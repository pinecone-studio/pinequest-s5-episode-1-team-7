"""Export the trained checkpoint to model/model_fp32.onnx (step 3) and check it against PyTorch.

ONNX graph contract, for the inference runner (step 5):
  input  "patches"      float32 (N, 3, S, S), RGB in [0, 1], S = metadata "input_size"
  output "p_malignant"  float32 (N,), probability in [0, 1]
ImageNet normalisation and the sigmoid are inside the graph. With --tta N the graph also
averages each patch over N orientations (metadata "tta_views"); same contract, N x compute.

    python -m training.export_onnx
    python -m training.export_onnx --checkpoint model/pcam_mobilenet_v3_small_96.pt --tta 4
    python -m training.export_onnx --checkpoint model/colon_mobilenet_v3_small_224_kd-hibou.pt         --out model/colon/model_fp32.onnx --results training/results/colon_mobilenet_v3_small_224_kd-hibou.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

from training.model import ProbabilityModel, TTAModel, build_model
from training.pcam import DATASETS

ENGINE_DIR = Path(__file__).resolve().parents[1]
INPUT_NAME, OUTPUT_NAME = "patches", "p_malignant"


def export(checkpoint_path: Path, out_path: Path, metadata: dict = None, tta: int = 1) -> Path:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model = build_model(checkpoint["arch"], pretrained=False)
    model.load_state_dict(checkpoint["state_dict"])
    net = (TTAModel(ProbabilityModel(model), tta) if tta > 1 else ProbabilityModel(model)).eval()
    size = checkpoint["img_size"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        net,
        (torch.rand(2, 3, size, size),),
        str(out_path),
        input_names=[INPUT_NAME],
        output_names=[OUTPUT_NAME],
        dynamic_shapes={"x": {0: torch.export.Dim("batch")}},
        dynamo=True,
        external_data=False,  # keep the weights inside the one .onnx file
        verbose=False,        # its progress output contains emoji that crash cp1252 Windows consoles
    )

    graph = onnx.load(str(out_path))
    onnx.checker.check_model(graph)
    info = {"arch": checkpoint["arch"], "input_size": str(size), "val_auc": f"{checkpoint['val_auc']:.4f}", "tta_views": str(tta), **(metadata or {})}
    for key, value in info.items():
        graph.metadata_props.add(key=key, value=str(value))
    onnx.save(graph, str(out_path))

    max_diff = check_against_torch(net, out_path, size)
    print(f"exported {out_path} ({out_path.stat().st_size / 1e6:.1f} MB), max |onnx - torch| = {max_diff:.2e}")
    return out_path


def check_against_torch(net: torch.nn.Module, onnx_path: Path, size: int, batch: int = 8) -> float:
    """Run both models on the same random batch; raise if the outputs differ."""
    x = torch.rand(batch, 3, size, size)
    with torch.no_grad():
        expected = net(x).numpy()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    actual = session.run([OUTPUT_NAME], {INPUT_NAME: x.numpy()})[0]
    max_diff = float(np.abs(actual - expected).max())
    if actual.shape != (batch,) or max_diff > 1e-4:
        raise RuntimeError(f"ONNX output does not match PyTorch: shape {actual.shape}, max diff {max_diff}")
    return max_diff


def main():
    p = argparse.ArgumentParser(description="Export the trained checkpoint to ONNX.")
    p.add_argument("--checkpoint", type=Path, default=ENGINE_DIR / "model" / "pcam_mobilenet_v3_small_224.pt")
    p.add_argument("--out", type=Path, default=ENGINE_DIR / "model" / "model_fp32.onnx")
    p.add_argument("--tta", type=int, default=1, help="orientations averaged inside the graph (1-8)")
    p.add_argument("--results", type=Path, help="training results JSON; its test metrics go into the ONNX metadata")
    args = p.parse_args()

    dataset = DATASETS["pcam"]
    metadata = {}
    if args.results:
        results = json.loads(args.results.read_text())
        dataset = DATASETS[results["config"].get("dataset", "pcam")]
        test = results["test"]
        metadata = {"test_auc": f"{test['auc']:.4f}", "test_accuracy": f"{test['accuracy']:.4f}"}
        if results.get("teacher"):
            metadata["distilled_from"] = results["teacher"]
    export(args.checkpoint, args.out, {"dataset": dataset["short"], "organ": dataset["organ"], **metadata}, tta=args.tta)


if __name__ == "__main__":
    main()
