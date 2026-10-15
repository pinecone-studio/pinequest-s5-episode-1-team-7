"""Foundation-model teacher for distillation: frozen backbone + a linear head per dataset.

The backbone turns a patch into a feature vector; a linear head on those features gives the
teacher's P_malignant. train.py --teacher <name> then trains the small student (MobileNetV3)
to match the teacher on the same augmented images, so the shipped model stays 6 MB.

Supported teachers (open licences, gated on Hugging Face: accept the terms and `hf auth login`):
  hibou-b      histai/hibou-b, Apache 2.0, ViT-B/14 with registers, 86M params

Weights load into transformers' built-in Dinov2WithRegistersModel, so no repository code is
executed. Downloads go to HF_HUB_CACHE (set it to a roomy disk, e.g. B:/pinequest-data/hf-cache/hub).

    python -m training.teacher --teacher hibou-b                     # PCam (lymph node)
    python -m training.teacher --teacher hibou-b --dataset nct_crc   # colon: its own head
    python -m training.teacher --teacher hibou-b --benchmark          # CPU speed + size, for the model card
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn

from training.pcam import DATASETS, PCamBatches, make_loader, to_input

ENGINE_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = ENGINE_DIR / "data" / "cache"   # teacher features (large, not in git)
MODEL_DIR = ENGINE_DIR / "model"            # teacher head (3 KB, committed)
RESULTS_DIR = ENGINE_DIR / "training" / "results"
INPUT_SIZE = 224

TEACHERS = {
    "hibou-b": {
        "repo": "histai/hibou-b",
        "mean": (0.7068, 0.5755, 0.722),
        "std": (0.195, 0.2316, 0.1816),
        "dim": 768,
    },
}


def load_backbone(name: str) -> nn.Module:
    """The frozen feature extractor; forward(x) takes the backbone's normalised input."""
    from huggingface_hub import hf_hub_download
    from transformers import Dinov2WithRegistersConfig, Dinov2WithRegistersModel

    repo = TEACHERS[name]["repo"]
    cfg = json.load(open(hf_hub_download(repo, "config.json")))
    skip = ("architectures", "auto_map", "model_type", "torch_dtype", "transformers_version")
    config = Dinov2WithRegistersConfig(**{k: v for k, v in cfg.items() if k not in skip})
    model, info = Dinov2WithRegistersModel.from_pretrained(repo, config=config, output_loading_info=True)
    if any(info[k] for k in ("missing_keys", "unexpected_keys", "mismatched_keys")):
        raise RuntimeError(f"{repo} weights did not load cleanly: {info}")
    return model.eval().requires_grad_(False)


class Teacher(nn.Module):
    """RGB float NCHW in [0, 1] at 224 px -> (features, logit of P_malignant)."""

    def __init__(self, name: str, head: nn.Linear = None):
        super().__init__()
        spec = TEACHERS[name]
        self.name = name
        self.backbone = load_backbone(name)
        self.register_buffer("mean", torch.tensor(spec["mean"]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(spec["std"]).view(1, 3, 1, 1))
        self.head = head if head is not None else nn.Linear(spec["dim"], 1)

    @torch.no_grad()
    def features(self, x: torch.Tensor) -> torch.Tensor:
        """CLS token after the final layer norm."""
        return self.backbone(pixel_values=(x - self.mean) / self.std).pooler_output

    @torch.no_grad()
    def logits(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x).float()).squeeze(1)


def _suffix(name: str, dataset: str) -> str:
    """File-name part for a teacher on a dataset; PCam keeps the original names (teacher_hibou-b_...)."""
    return name if dataset == "pcam" else f"{name}_{dataset}"


def head_path(name: str, dataset: str = "pcam") -> Path:
    return MODEL_DIR / f"teacher_{_suffix(name, dataset)}_head.pt"


def features_path(name: str, split: str, dataset: str = "pcam") -> Path:
    return CACHE_DIR / f"teacher_{_suffix(name, dataset)}_{split}.npz"


def load_teacher(name: str, device, dataset: str = "pcam") -> Teacher:
    """Teacher with its trained head, ready for distillation."""
    path = head_path(name, dataset)
    if not path.exists():
        raise FileNotFoundError(
            f"no head for teacher {name!r} on {dataset}: run `python -m training.teacher --teacher {name} --dataset {dataset}` first"
        )
    head = nn.Linear(TEACHERS[name]["dim"], 1)
    head.load_state_dict(torch.load(path, map_location="cpu"))
    return Teacher(name, head).to(device).eval()


def extract(teacher: Teacher, split: str, data_dir: Path, device, batch_size: int, workers: int, dataset_name: str = "pcam") -> tuple:
    """(features float16 (N, dim), labels) for a dataset split, cached on disk."""
    cache = features_path(teacher.name, split, dataset_name)
    if cache.exists():
        data = np.load(cache)
        return data["features"], data["labels"]
    dataset = PCamBatches.from_split(split, data_dir, dataset=dataset_name)
    feats = []
    for i, (images, _) in enumerate(make_loader(dataset, batch_size, shuffle=False, workers=workers)):
        x = to_input(images, device, INPUT_SIZE)
        with torch.autocast(device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
            feats.append(teacher.features(x).float().cpu().numpy().astype(np.float16))
        if (i + 1) % 100 == 0:
            print(f"\r  {split}: {(i + 1) * batch_size}/{len(dataset)}", end="", flush=True)
    print()
    features, labels = np.concatenate(feats), dataset.labels.astype(np.float32)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(cache, features=features, labels=labels)
    return features, labels


def fit_head(train: tuple, valid: tuple, dim: int, device, epochs: int = 20) -> tuple:
    """Logistic-regression head on frozen features; keeps the epoch with the best validation AUC."""
    x, y = (torch.from_numpy(a).to(device) for a in (train[0].astype(np.float32), train[1]))
    xv = torch.from_numpy(valid[0].astype(np.float32)).to(device)
    head = nn.Linear(dim, 1).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    best_auc, best_state = -1.0, None
    for epoch in range(epochs):
        order = torch.randperm(len(x), device=device)
        for i in range(0, len(x), 1024):
            idx = order[i:i + 1024]
            loss = nn.functional.binary_cross_entropy_with_logits(head(x[idx]).squeeze(1), y[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        with torch.no_grad():
            auc = roc_auc_score(valid[1], head(xv).squeeze(1).cpu().numpy())
        if auc > best_auc:
            best_auc, best_state = auc, {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}
    head.load_state_dict(best_state)
    return head.cpu(), best_auc


def benchmark(name: str, patches: int = 150, batch: int = 16, threads: int = 4, runs: int = 3) -> dict:
    """CPU seconds per slide and weights size, measured like the shipped model's (training/quantize.py).

    The teacher is the accuracy ceiling the student was distilled from; this records why it isn't the
    model the clinic PC runs.
    """
    import time

    from huggingface_hub import hf_hub_download

    torch.set_num_threads(threads)
    teacher = Teacher(name).eval()
    x = torch.rand(patches, 3, INPUT_SIZE, INPUT_SIZE)
    with torch.no_grad():
        teacher.features(x[:batch])  # warm-up
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            for i in range(0, patches, batch):
                teacher.features(x[i:i + batch])
            times.append(time.perf_counter() - start)
    weights = Path(hf_hub_download(TEACHERS[name]["repo"], "model.safetensors"))
    return {
        "cpu_seconds_per_slide": round(sorted(times)[len(times) // 2], 1),
        "size_mb": round(weights.stat().st_size / 1e6),
        "benchmark": f"median of {runs} warm runs, {patches} patches, batch {batch}, {threads} threads, "
                     f"PyTorch {torch.__version__}, frozen backbone only",
    }


def main():
    p = argparse.ArgumentParser(description="Extract teacher features on a dataset and train its linear head.")
    p.add_argument("--teacher", choices=TEACHERS, default="hibou-b")
    p.add_argument("--dataset", choices=DATASETS, default="pcam")
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--data-dir", type=Path, help="default: the dataset's folder (training/pcam.py DATASETS)")
    p.add_argument("--benchmark", action="store_true", help="only measure CPU speed + size into the teacher's results file")
    args = p.parse_args()

    if args.benchmark:
        out = RESULTS_DIR / f"teacher_{args.teacher}.json"
        result = json.loads(out.read_text()) if out.exists() else {"teacher": args.teacher}
        result["cpu"] = benchmark(args.teacher)
        print(json.dumps(result["cpu"], indent=2))
        out.write_text(json.dumps(result, indent=2))
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    teacher = Teacher(args.teacher).to(device)
    data = {s: extract(teacher, s, args.data_dir, device, args.batch_size, args.workers, args.dataset) for s in ("train", "valid", "test")}

    head, val_auc = fit_head(data["train"], data["valid"], TEACHERS[args.teacher]["dim"], device)
    torch.save(head.state_dict(), head_path(args.teacher, args.dataset))
    with torch.no_grad():
        test_p = torch.sigmoid(head(torch.from_numpy(data["test"][0].astype(np.float32))).squeeze(1)).numpy()
    test_y = data["test"][1]
    result = {
        "teacher": args.teacher, "repo": TEACHERS[args.teacher]["repo"], "dataset": args.dataset,
        "valid_auc": float(val_auc), "test_auc": float(roc_auc_score(test_y, test_p)),
        "test_accuracy": float(((test_p >= 0.5) == (test_y == 1)).mean()),
    }
    print(json.dumps(result, indent=2))
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"teacher_{_suffix(args.teacher, args.dataset)}.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
