"""Fine-tune the patch classifier on PCam (step 3).

Trains with strong augmentation and an exponential moving average (EMA) of the weights,
picks the epoch whose EMA weights score the best validation AUC, then evaluates that
checkpoint once on the held-out test split, with and without test-time augmentation (TTA).
Writes:
  - model/pcam_<arch>_<size>[_<tag>].pt                best checkpoint (not committed)
  - training/results/pcam_<arch>_<size>[_<tag>].json  config, history and test metrics

    python -m training.download_pcam
    python -m training.train                       # MobileNetV3-Small, 224 px, 8 epochs (~25 min on an RTX 4060)
    python -m training.train --img-size 96         # native PCam size: 5x faster, lower AUC
    python -m training.train --limit 4096 --epochs 1   # quick smoke test
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn
from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn

from training.model import ARCHS, ProbabilityModel, build_model, tta_views
from training.pcam import DATA_DIR, PCamBatches, augment, make_loader, to_input

ENGINE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = ENGINE_DIR / "model"
RESULTS_DIR = ENGINE_DIR / "training" / "results"
TARGET_SENSITIVITY = 0.90  # reported operating point, for the step 6 threshold discussion


def parse_args():
    p = argparse.ArgumentParser(description="Fine-tune the patch classifier on PCam.")
    p.add_argument("--arch", choices=ARCHS, default="mobilenet_v3_small")
    p.add_argument("--img-size", type=int, default=224, help="model input size; PCam patches (96 px) are upsampled to it")
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument("--weight-decay", type=float, default=0.05)
    p.add_argument("--aug-strength", type=float, default=1.0, help="0 = flips/rotations only")
    p.add_argument("--ema-decay", type=float, default=0.999, help="0 disables EMA")
    p.add_argument("--tta", type=int, default=8, choices=range(1, 9), help="views for the final TTA evaluation")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit", type=int, default=0, help="use only the first N samples of each split")
    p.add_argument("--tag", default="", help="appended to output file names")
    p.add_argument("--teacher", default="", help="distil from this teacher (training/teacher.py), e.g. hibou-b")
    p.add_argument("--kd-alpha", type=float, default=0.5, help="weight of the true labels; 1 - alpha goes to the teacher")
    p.add_argument("--kd-temp", type=float, default=2.0, help="softens teacher and student logits for the distillation loss")
    p.add_argument("--data-dir", type=Path, default=DATA_DIR)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


@torch.no_grad()
def predict(net: ProbabilityModel, loader, device, img_size: int, views: int = 1) -> tuple:
    """Return (P_malignant averaged over `views` orientations, labels) over the whole loader."""
    net.eval()
    probs, labels = [], []
    for images, y in loader:
        x = to_input(images, device, img_size)
        with torch.autocast(device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
            p = torch.stack([net(v).float() for v in tta_views(x, views)]).mean(0)
        probs.append(p.cpu())
        labels.append(y)
    return torch.cat(probs).numpy(), torch.cat(labels).numpy()


def metrics(probs: np.ndarray, labels: np.ndarray, threshold: float = 0.5) -> dict:
    pred = probs >= threshold
    pos = labels == 1
    return {
        "auc": float(roc_auc_score(labels, probs)),
        "accuracy": float((pred == pos).mean()),
        "sensitivity": float(pred[pos].mean()),    # malignant patches caught
        "specificity": float((~pred[~pos]).mean()),  # benign patches correctly passed
        "threshold": float(threshold),
        "n": int(len(labels)),
    }


def threshold_for_sensitivity(probs: np.ndarray, labels: np.ndarray, sensitivity: float) -> float:
    """Highest threshold that still flags `sensitivity` of the positives."""
    return float(np.quantile(probs[labels == 1], 1.0 - sensitivity))


def teacher_logits(name: str, limit: int = 0) -> np.ndarray:
    """Teacher logit for every training image, from its cached features and head."""
    from training.teacher import CACHE_DIR, TEACHERS, head_path

    features = np.load(CACHE_DIR / f"teacher_{name}_train.npz")["features"]
    head = nn.Linear(TEACHERS[name]["dim"], 1)
    head.load_state_dict(torch.load(head_path(name), map_location="cpu"))
    with torch.no_grad():
        logits = head(torch.from_numpy(features.astype(np.float32))).squeeze(1).numpy()
    return logits[:limit] if limit else logits


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {torch.cuda.get_device_name(0) if device.type == 'cuda' else 'cpu'}")

    data = {s: PCamBatches.from_split(s, args.data_dir, args.limit) for s in ("train", "valid", "test")}
    train_loader = make_loader(data["train"], args.batch_size, shuffle=True, workers=args.workers)
    eval_loaders = {s: make_loader(data[s], args.batch_size * 2, False, args.workers) for s in ("valid", "test")}
    print({s: len(d) for s, d in data.items()})

    net = ProbabilityModel(build_model(args.arch, pretrained=True)).to(device).to(memory_format=torch.channels_last)
    ema = AveragedModel(net, multi_avg_fn=get_ema_multi_avg_fn(args.ema_decay), use_buffers=True) if args.ema_decay else None
    eval_net = ema.module if ema else net
    optimizer = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=args.lr, total_steps=args.epochs * len(train_loader), pct_start=0.1
    )
    loss_fn = nn.BCEWithLogitsLoss()
    if args.teacher:
        data["train"].soft = teacher_logits(args.teacher, args.limit)
        print(f"distilling from {args.teacher}: alpha {args.kd_alpha}, temperature {args.kd_temp}")

    # Smoke runs (--limit) never overwrite real results.
    name = f"pcam_{args.arch}_{args.img_size}" + (f"_{args.tag}" if args.tag else "") + (f"_limit{args.limit}" if args.limit else "")
    MODEL_DIR.mkdir(exist_ok=True)
    checkpoint_path = MODEL_DIR / f"{name}.pt"
    history, best_auc = [], -1.0

    for epoch in range(1, args.epochs + 1):
        net.train()
        start, total_loss, steps = time.perf_counter(), 0.0, 0
        for images, y, *soft in train_loader:
            x = augment(to_input(images, device, args.img_size), args.aug_strength)
            y = y.to(device, non_blocking=True)
            with torch.autocast(device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                logits = net.logits(x).float()
            loss = loss_fn(logits, y)
            if soft:
                # Offline distillation: the teacher's view of the clean image is the target for the
                # augmented one, so the student also learns to ignore stain, blur and lighting changes.
                t = args.kd_temp
                target = torch.sigmoid(soft[0].to(device, non_blocking=True) / t)
                loss = args.kd_alpha * loss + (1 - args.kd_alpha) * t * t * loss_fn(logits / t, target)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            scheduler.step()
            if ema:
                ema.update_parameters(net)
            total_loss += loss.item()
            steps += 1
            if steps % 100 == 0:
                print(f"  epoch {epoch} step {steps}/{len(train_loader)} loss {total_loss / steps:.4f}", flush=True)

        val = metrics(*predict(eval_net, eval_loaders["valid"], device, args.img_size))
        row = {"epoch": epoch, "train_loss": total_loss / steps, "seconds": time.perf_counter() - start, **{f"val_{k}": v for k, v in val.items()}}
        history.append(row)
        print(f"epoch {epoch}: loss {row['train_loss']:.4f}  val AUC {val['auc']:.4f}  acc {val['accuracy']:.4f}  ({row['seconds']:.0f}s)", flush=True)

        if val["auc"] > best_auc:
            best_auc = val["auc"]
            torch.save(
                {"arch": args.arch, "img_size": args.img_size, "epoch": epoch, "val_auc": best_auc, "state_dict": eval_net.model.state_dict()},
                checkpoint_path,
            )

    best = torch.load(checkpoint_path, map_location=device)
    eval_net.model.load_state_dict(best["state_dict"])

    evaluation = {}
    for views in sorted({1, args.tta}):
        val_probs, val_labels = predict(eval_net, eval_loaders["valid"], device, args.img_size, views)
        test_probs, test_labels = predict(eval_net, eval_loaders["test"], device, args.img_size, views)
        threshold = threshold_for_sensitivity(val_probs, val_labels, TARGET_SENSITIVITY)
        evaluation[f"tta{views}"] = {
            "valid": metrics(val_probs, val_labels),
            "test": metrics(test_probs, test_labels),
            # Threshold chosen on validation for 90% sensitivity, then applied to test.
            f"test_at_val_{int(TARGET_SENSITIVITY * 100)}_sensitivity": metrics(test_probs, test_labels, threshold),
        }
        t = evaluation[f"tta{views}"]["test"]
        print(f"best epoch {best['epoch']}, TTA x{views}: test AUC {t['auc']:.4f}  acc {t['accuracy']:.4f}")

    RESULTS_DIR.mkdir(exist_ok=True)
    result = {
        "dataset": "PatchCamelyon (PCam), CC0, via Hugging Face 1aurent/PatchCamelyon",
        "teacher": args.teacher or None,
        "config": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k != "data_dir"},
        "best_epoch": best["epoch"],
        "valid": evaluation["tta1"]["valid"],
        "test": evaluation["tta1"]["test"],
        "evaluation": evaluation,
        "history": history,
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
    }
    out = RESULTS_DIR / f"{name}.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"checkpoint: {checkpoint_path}\nresults: {out}")


if __name__ == "__main__":
    main()
