"""Estimate per-slide CPU time of the published PCam baselines (training/results/literature_pcam.json).

The papers report accuracy, not speed. To compare them fairly on the About page, a DenseNet
with the same parameter count as Veeling et al.'s (128K, torchvision's DenseNet with growth
rate 10 and blocks (6, 6, 6)) is exported to ONNX and timed exactly like the shipped model
(training/quantize.py): ONNX Runtime, CPU, 4 threads, batch 16, 150 patches, median of warm
runs. Patches are PCam's native 96 px, which cover the same tissue area as one of our 224 px
tiles at 0.42 µm/px.
  - Veeling's exact first layers ("stem") aren't published in a form we can rebuild, and they
    change the cost ~16x, so both ends are timed: torchvision's 7x7 stride-2 convolution +
    max-pool (fast end) and a 3x3 convolution with no downsampling (slow end). The estimate is
    their geometric mean, shown with the range.
  - P4M-DenseNet's rotation-equivariant layers apply every weight in 8 orientations, so it
    costs ~8x a plain DenseNet's computation per parameter: estimated as the measured DenseNet
    time x 8 x (119K / 128K). Not run, because it needs the GrouPy library.

    python -m training.benchmark_baselines      # writes the estimates into literature_pcam.json
"""
import json
import tempfile
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from torch import nn
from torchvision.models import DenseNet

RESULTS = Path(__file__).resolve().parents[1] / "training" / "results" / "literature_pcam.json"
PATCHES, BATCH, THREADS, RUNS, SIZE = 150, 16, 4, 5, 96
P4M_COST_PER_PARAM = 8  # |p4m| = 4 rotations x 2 reflections
LOCAL_BUDGET_S = 1.5    # TDD: under 1.5 s per slide on a clinic CPU


def densenet_proxy(full_resolution_stem: bool) -> nn.Module:
    model = DenseNet(growth_rate=10, block_config=(6, 6, 6), num_init_features=24, bn_size=4, num_classes=1)
    if full_resolution_stem:
        model.features.conv0 = nn.Conv2d(3, 24, kernel_size=3, padding=1, bias=False)
        model.features.pool0 = nn.Identity()
    return model.eval()


def seconds_per_slide(model: nn.Module) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "proxy.onnx"
        torch.onnx.export(model, (torch.rand(2, 3, SIZE, SIZE),), str(path), input_names=["x"],
                          dynamic_shapes={"x": {0: torch.export.Dim("batch")}}, dynamo=True,
                          external_data=False, verbose=False)
        options = ort.SessionOptions()
        options.intra_op_num_threads = THREADS
        session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        x = np.random.rand(PATCHES, 3, SIZE, SIZE).astype(np.float32)
        run = lambda: [session.run(None, {"x": x[i:i + BATCH]}) for i in range(0, PATCHES, BATCH)]  # noqa: E731
        run()  # warm-up
        times = []
        for _ in range(RUNS):
            start = time.perf_counter()
            run()
            times.append(time.perf_counter() - start)
    return float(np.median(times))


def main():
    literature = json.loads(RESULTS.read_text(encoding="utf-8"))
    ends = []  # (seconds per slide, parameter count) for the fast and the slow stem
    for full in (False, True):
        model = densenet_proxy(full)
        ends.append((seconds_per_slide(model), sum(p.numel() for p in model.parameters())))
    method = (f"estimated on this PC with a DenseNet of the same size (ONNX Runtime, CPU, {THREADS} threads, "
              f"{PATCHES} patches of {SIZE} px, median of {RUNS}); not the published network")
    for b in literature["baselines"]:
        factor = P4M_COST_PER_PARAM if b["model"].startswith("P4M") else 1
        low, high = (round(t * factor * b["params"] / n, 2) for t, n in ends)
        b["per_slide_s"] = round(float(np.sqrt(low * high)), 2)
        b["per_slide_range_s"] = [low, high]
        b["speed_method"] = method + (f"; x{P4M_COST_PER_PARAM} for rotation-equivariant layers" if factor > 1 else "")
        # Small CNNs: they run on a clinic CPU; "slow" if the estimate misses the TDD budget.
        b["local"] = "yes" if b["per_slide_s"] <= LOCAL_BUDGET_S else "slow"
        b.pop("clinic_pc", None)
        print(f"{b['model']}: ~{b['per_slide_s']} s per slide ({low}-{high}), local: {b['local']}")
    RESULTS.write_text(json.dumps(literature, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
