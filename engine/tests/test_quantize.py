"""INT8 quantization (step 4). Skipped unless the training extras (requirements-train.txt) are installed."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("onnx")
pytest.importorskip("sklearn")

import onnx  # noqa: E402
import onnxruntime as ort  # noqa: E402
from onnxruntime.quantization import CalibrationDataReader  # noqa: E402

from training.export_onnx import INPUT_NAME, OUTPUT_NAME, export  # noqa: E402
from training.model import build_model  # noqa: E402
from training.quantize import input_size, quantize  # noqa: E402


class RandomCalibration(CalibrationDataReader):
    def __init__(self, batches=4, size=96):
        rng = np.random.default_rng(0)
        self.batches = iter([rng.random((4, 3, size, size), dtype=np.float32) for _ in range(batches)])

    def get_next(self):
        batch = next(self.batches, None)
        return None if batch is None else {INPUT_NAME: batch}


@pytest.fixture(scope="module")
def fp32_model(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("quant")
    checkpoint = tmp / "ckpt.pt"
    model = build_model("mobilenet_v3_small", pretrained=False)
    torch.save({"arch": "mobilenet_v3_small", "img_size": 96, "val_auc": 0.5, "state_dict": model.state_dict()}, checkpoint)
    return export(checkpoint, tmp / "model_fp32.onnx")


def test_input_size_reads_graph(fp32_model):
    assert input_size(fp32_model) == 96


def test_int8_model_runs_with_same_contract(fp32_model, tmp_path):
    int8 = quantize(fp32_model, tmp_path / "model_int8.onnx", RandomCalibration(), fp32_convs=10)

    session = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"])
    out = session.run([OUTPUT_NAME], {INPUT_NAME: np.random.rand(5, 3, 96, 96).astype(np.float32)})[0]

    assert out.shape == (5,)
    assert ((out >= 0) & (out <= 1)).all()
    assert int8.stat().st_size < fp32_model.stat().st_size / 2
    assert not (tmp_path / "model_int8_prep.onnx").exists()  # temp file cleaned up


def test_first_convs_stay_fp32_and_metadata_is_kept(fp32_model, tmp_path):
    int8 = quantize(fp32_model, tmp_path / "model_int8.onnx", RandomCalibration(), fp32_convs=3)

    graph = onnx.load(str(int8)).graph
    # A quantized conv reads its weight through a DequantizeLinear node; an FP32 one does not.
    dequantized = {n.output[0] for n in graph.node if n.op_type == "DequantizeLinear"}
    convs = [n for n in graph.node if n.op_type == "Conv"]
    assert [n.input[1] in dequantized for n in convs[:4]] == [False, False, False, True]

    meta = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"]).get_modelmeta().custom_metadata_map
    assert meta["input_size"] == "96"
    assert "first 3 convs FP32" in meta["quantization"]
