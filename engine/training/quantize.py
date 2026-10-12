"""Quantize model_fp32.onnx to INT8 (step 4, TDD 5.2) and compare it with FP32.

Static quantization (QDQ format) calibrated on PCam training patches, then both models are
scored on the PCam test split and timed on CPU. Writes:
  - model/model_int8.onnx                     (not committed, see .gitignore)
  - training/results/int8_<name>.json         size, AUC and latency, FP32 vs INT8

    python -m training.quantize                     # first 10 convs FP32, per-channel, MinMax, reduce-range
    python -m training.quantize --fp32-convs 0      # quantize every conv (fine for ResNet-18)

Only Conv and Gemm are quantized. MobileNetV3's first layers must stay FP32: a few channels
of the first conv have much larger values than the rest, so a shared 8-bit scale wipes out
the small channels and the next depthwise conv amplifies the error (test AUC 0.96 -> ~0.5).

Reduce-range (7-bit weights) is the default: on x86 CPUs without VNNI (e.g. 8th-gen Intel
i3, the TDD's minimum spec) ONNX Runtime's U8S8 kernels can saturate with full 8-bit
weights, which a VNNI CPU like the dev machine would never show.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.quantization import CalibrationDataReader, CalibrationMethod, QuantFormat, QuantType, quantize_static
from onnxruntime.quantization.shape_inference import quant_pre_process
from sklearn.metrics import roc_auc_score

from training.export_onnx import INPUT_NAME, OUTPUT_NAME
from training.pcam import DATA_DIR, PCamBatches, to_input

ENGINE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = ENGINE_DIR / "model"
RESULTS_DIR = ENGINE_DIR / "training" / "results"
METHODS = {"minmax": CalibrationMethod.MinMax, "percentile": CalibrationMethod.Percentile, "entropy": CalibrationMethod.Entropy}
BENCH_PATCHES = 150  # tissue patches in a typical 12 MP capture, as in the step 3 benchmark
BENCH_THREADS = 4    # quad-core clinic PC (TDD 5.1)


def input_size(model_path: Path) -> int:
    return int(onnx.load(str(model_path)).graph.input[0].type.tensor_type.shape.dim[2].dim_value)


def load_patches(dataset: PCamBatches, indices, size: int) -> np.ndarray:
    """PCam samples -> float32 NCHW [0, 1] at the model's input size (same as training)."""
    images, _ = dataset[list(indices)]
    return np.ascontiguousarray(to_input(images, "cpu", size).numpy())


class PCamCalibration(CalibrationDataReader):
    """Feeds `samples` random training patches to the calibrator, `batch` at a time."""

    def __init__(self, dataset: PCamBatches, size: int, samples: int, batch: int = 32, seed: int = 0):
        indices = np.sort(np.random.default_rng(seed).choice(len(dataset), samples, replace=False))
        self.batches = iter([load_patches(dataset, indices[i:i + batch], size) for i in range(0, samples, batch)])

    def get_next(self):
        batch = next(self.batches, None)
        return None if batch is None else {INPUT_NAME: batch}


def quantize(fp32_path: Path, int8_path: Path, calibration: CalibrationDataReader, method: str = "minmax",
             per_channel: bool = True, reduce_range: bool = True, fp32_convs: int = 10) -> Path:
    """Quantize Conv and Gemm nodes, except the first `fp32_convs` convolutions."""
    prepared = int8_path.with_name(int8_path.stem + "_prep.onnx")
    quant_pre_process(str(fp32_path), str(prepared))  # shape inference + graph cleanup, as ORT recommends
    convs = [n.name for n in onnx.load(str(prepared)).graph.node if n.op_type == "Conv"]
    try:
        quantize_static(
            str(prepared),
            str(int8_path),
            calibration,
            quant_format=QuantFormat.QDQ,
            per_channel=per_channel,
            reduce_range=reduce_range,
            activation_type=QuantType.QUInt8,
            weight_type=QuantType.QInt8,
            calibrate_method=METHODS[method],
            op_types_to_quantize=["Conv", "Gemm"],
            nodes_to_exclude=convs[:fp32_convs],
        )
    finally:
        prepared.unlink(missing_ok=True)

    # Carry the FP32 model's metadata over (input_size, arch, ...) and record the quantization.
    fp32, int8 = onnx.load(str(fp32_path)), onnx.load(str(int8_path))
    meta = {p.key: p.value for p in fp32.metadata_props}
    meta.update({"quantization": f"int8 static QDQ (Conv, Gemm), {method}, per_channel={per_channel}, "
                 f"reduce_range={reduce_range}, first {fp32_convs} convs FP32"})
    del int8.metadata_props[:]
    for key, value in meta.items():
        int8.metadata_props.add(key=key, value=value)
    onnx.save(int8, str(int8_path))
    return int8_path


def session(model_path: Path, threads: int = 0) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    return ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])


def evaluate(model_path: Path, dataset: PCamBatches, size: int, batch: int = 256) -> float:
    """AUC on the whole split."""
    sess, probs = session(model_path), []
    for start in range(0, len(dataset), batch):
        x = load_patches(dataset, range(start, min(start + batch, len(dataset))), size)
        probs.append(sess.run([OUTPUT_NAME], {INPUT_NAME: x})[0])
    return float(roc_auc_score(dataset.labels, np.concatenate(probs)))


def benchmark(model_path: Path, size: int, repeats: int = 5) -> float:
    """Median seconds to score BENCH_PATCHES patches in batches of 16 on BENCH_THREADS threads."""
    sess = session(model_path, BENCH_THREADS)
    x = np.random.default_rng(0).random((16, 3, size, size), dtype=np.float32)
    sess.run([OUTPUT_NAME], {INPUT_NAME: x})  # warm-up
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        for i in range(0, BENCH_PATCHES, 16):
            sess.run([OUTPUT_NAME], {INPUT_NAME: x[: min(16, BENCH_PATCHES - i)]})
        times.append(time.perf_counter() - start)
    return float(np.median(times))


def main():
    p = argparse.ArgumentParser(description="Quantize the FP32 ONNX model to INT8 and compare.")
    p.add_argument("--fp32", type=Path, default=MODEL_DIR / "model_fp32.onnx")
    p.add_argument("--out", type=Path, default=MODEL_DIR / "model_int8.onnx")
    p.add_argument("--method", choices=METHODS, default="minmax")
    p.add_argument("--calib-samples", type=int, default=512)
    p.add_argument("--no-per-channel", dest="per_channel", action="store_false")
    p.add_argument("--no-reduce-range", dest="reduce_range", action="store_false")
    p.add_argument("--fp32-convs", type=int, default=10, help="leave the first N convolutions in FP32")
    p.add_argument("--eval-limit", type=int, default=0, help="score only the first N test patches")
    p.add_argument("--name", default="", help="results file suffix; defaults to the settings")
    p.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = p.parse_args()

    size = input_size(args.fp32)
    calibration = PCamCalibration(PCamBatches.from_split("train", args.data_dir), size, args.calib_samples)
    quantize(args.fp32, args.out, calibration, args.method, args.per_channel, args.reduce_range, args.fp32_convs)

    test = PCamBatches.from_split("test", args.data_dir, args.eval_limit)
    report = {}
    for label, path in (("fp32", args.fp32), ("int8", args.out)):
        report[label] = {
            "size_mb": round(path.stat().st_size / 1e6, 2),
            "test_auc": round(evaluate(path, test, size), 4),
            "seconds_per_slide": round(benchmark(path, size), 3),
        }
        print(f"{label}: {report[label]}", flush=True)
    report["size_reduction"] = round(1 - report["int8"]["size_mb"] / report["fp32"]["size_mb"], 3)
    report["auc_drop"] = round(report["fp32"]["test_auc"] - report["int8"]["test_auc"], 4)
    report["speedup"] = round(report["fp32"]["seconds_per_slide"] / report["int8"]["seconds_per_slide"], 2)
    report["config"] = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k not in ("data_dir", "fp32", "out")}
    report["benchmark"] = f"{BENCH_PATCHES} patches, batch 16, {BENCH_THREADS} threads, onnxruntime {ort.__version__}"
    print(f"size -{report['size_reduction']:.0%}, AUC drop {report['auc_drop']:+.4f}, speed-up x{report['speedup']}")

    name = args.name or f"{args.method}_fp32convs{args.fp32_convs}_{'pc' if args.per_channel else 'pt'}_{'rr' if args.reduce_range else 'full'}"
    if args.eval_limit:
        name += f"_limit{args.eval_limit}"
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"int8_{name}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"model: {args.out}\nresults: {out}")


if __name__ == "__main__":
    main()
