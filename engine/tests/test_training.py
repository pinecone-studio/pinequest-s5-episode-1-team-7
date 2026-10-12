"""Training/export code. Skipped unless the training extras (requirements-train.txt) are installed."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
h5py = pytest.importorskip("h5py")
pytest.importorskip("onnx")

from training.export_onnx import INPUT_NAME, OUTPUT_NAME, export  # noqa: E402
from training.model import ProbabilityModel, TTAModel, build_model, tta_views  # noqa: E402
from training.pcam import PCamBatches, _stain_jitter, augment, split_paths, to_input  # noqa: E402


def write_split(data_dir, split, n, seed=0):
    rng = np.random.default_rng(seed)
    images = rng.integers(0, 255, (n, 96, 96, 3), dtype=np.uint8)
    labels = rng.integers(0, 2, n).astype(np.uint8)
    x_path, y_path = split_paths(split, data_dir)
    with h5py.File(x_path, "w") as f:
        f.create_dataset("x", data=images)
    with h5py.File(y_path, "w") as f:
        f.create_dataset("y", data=labels.reshape(n, 1, 1, 1))
    return images, labels


def test_batches_return_requested_samples(tmp_path):
    images, labels = write_split(tmp_path, "valid", 10)
    data = PCamBatches.from_split("valid", tmp_path)

    x, y = data[[7, 2, 5]]

    assert len(data) == 10
    np.testing.assert_array_equal(x.numpy(), images[[2, 5, 7]])  # returned in sorted order
    np.testing.assert_array_equal(y.numpy(), labels[[2, 5, 7]].astype(np.float32))


def test_limit_truncates_split(tmp_path):
    write_split(tmp_path, "train", 10)
    assert len(PCamBatches.from_split("train", tmp_path, limit=4)) == 4


def test_to_input_and_augment_keep_shape_and_range():
    images = torch.randint(0, 256, (4, 96, 96, 3), dtype=torch.uint8)

    x = to_input(images, "cpu", img_size=128)
    out = augment(x)

    assert x.shape == out.shape == (4, 3, 128, 128)
    assert 0.0 <= out.min() and out.max() <= 1.0
    assert not torch.equal(out, x)


def test_stain_jitter_without_change_is_identity():
    x = torch.rand(2, 3, 16, 16) * 0.9 + 0.05

    torch.testing.assert_close(_stain_jitter(x, 2, sigma=0.0, bias=0.0), x, atol=1e-5, rtol=1e-5)


def test_tta_views_are_distinct_orientations():
    x = torch.rand(1, 3, 8, 8)

    views = list(tta_views(x, 8))

    assert torch.equal(views[0], x)
    assert len({tuple(v.flatten().tolist()) for v in views}) == 8
    with pytest.raises(ValueError):
        list(tta_views(x, 9))


@pytest.mark.parametrize("arch", ["mobilenet_v3_small", "resnet18"])
def test_probability_model_outputs_one_probability_per_patch(arch):
    net = ProbabilityModel(build_model(arch, pretrained=False)).eval()
    with torch.no_grad():
        p = net(torch.rand(3, 3, 96, 96))
    assert p.shape == (3,)
    assert ((p >= 0) & (p <= 1)).all()


def test_export_matches_pytorch(tmp_path):
    ort = pytest.importorskip("onnxruntime")
    checkpoint = tmp_path / "ckpt.pt"
    model = build_model("mobilenet_v3_small", pretrained=False)
    torch.save({"arch": "mobilenet_v3_small", "img_size": 96, "val_auc": 0.5, "state_dict": model.state_dict()}, checkpoint)

    path = export(checkpoint, tmp_path / "model.onnx")  # raises if ONNX and PyTorch disagree

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    out = session.run([OUTPUT_NAME], {INPUT_NAME: np.random.rand(5, 3, 96, 96).astype(np.float32)})[0]
    assert out.shape == (5,)
    meta = session.get_modelmeta().custom_metadata_map
    assert meta["input_size"] == "96" and meta["arch"] == "mobilenet_v3_small" and meta["tta_views"] == "1"


def test_tta_export_matches_pytorch(tmp_path):
    checkpoint = tmp_path / "ckpt.pt"
    model = build_model("mobilenet_v3_small", pretrained=False)
    torch.save({"arch": "mobilenet_v3_small", "img_size": 96, "val_auc": 0.5, "state_dict": model.state_dict()}, checkpoint)

    export(checkpoint, tmp_path / "model.onnx", tta=4)  # raises if ONNX and PyTorch disagree


def test_tta_model_averages_orientations():
    net = ProbabilityModel(build_model("mobilenet_v3_small", pretrained=False)).eval()
    x = torch.rand(2, 3, 96, 96)
    with torch.no_grad():
        expected = torch.stack([net(v) for v in tta_views(x, 4)]).mean(0)
        torch.testing.assert_close(TTAModel(net, 4)(x), expected)
