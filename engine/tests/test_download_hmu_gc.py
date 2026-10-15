"""Stomach data converter. Skipped unless cv2 + h5py are installed (no torch needed)."""
import zipfile

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
h5py = pytest.importorskip("h5py")

from training.download_hmu_gc import (  # noqa: E402
    CLASSES,
    TILE,
    TUMOUR,
    collect_tiles,
    decode,
    label_for_class,
    stratified_split,
    write_split,
)


def _tile(color=128):
    img = np.full((TILE, TILE, 3), color, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_label_for_class():
    assert label_for_class("TUM") == TUMOUR
    assert label_for_class("tum") == TUMOUR
    assert label_for_class("NOR") != TUMOUR
    with pytest.raises(ValueError):
        label_for_class("CANCER")


def test_collect_tiles_reads_class_folders(tmp_path):
    archive = tmp_path / "hmu.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("HMU-GC-HE-30K/all_image/TUM/a.png", _tile())
        zf.writestr("HMU-GC-HE-30K/all_image/NOR/b.png", _tile())
        zf.writestr("HMU-GC-HE-30K/preview.jpg", _tile())
    tiles = collect_tiles(archive)
    assert tiles == [
        ("HMU-GC-HE-30K/all_image/NOR/b.png", label_for_class("NOR")),
        ("HMU-GC-HE-30K/all_image/TUM/a.png", label_for_class("TUM")),
    ]


def test_decode_rejects_wrong_size():
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    with pytest.raises(ValueError, match="224"):
        decode(buf.tobytes())
    with pytest.raises(ValueError):
        decode(b"not an image")


def test_stratified_split_covers_every_class():
    rng = np.random.default_rng(0)
    labels = np.repeat(np.arange(4), 100)  # 100 tiles in each of 4 classes
    labels = labels[rng.permutation(len(labels))]
    train, valid, test = stratified_split(labels)
    assert len(train) == 320 and len(valid) == 40 and len(test) == 40
    assert len(set(train) | set(valid) | set(test)) == 400  # disjoint, complete
    for c in range(4):
        assert (labels[train] == c).sum() == 80
        assert (labels[valid] == c).sum() == 10
        assert (labels[test] == c).sum() == 10


def test_stratified_split_rejects_tiny_classes():
    with pytest.raises(ValueError):
        stratified_split(np.array([0, 1, 1, 1, 1, 1]))


def test_write_split_layout(tmp_path):
    images = np.stack([np.full((TILE, TILE, 3), c, dtype=np.uint8) for c in (10, 20, 30, 40)])
    classes = np.array([TUMOUR, 0, TUMOUR, 1], dtype=np.uint8)
    import training.download_hmu_gc as hmu
    orig_paths = hmu._split_paths

    def fake_paths(split, data_dir):
        return tmp_path / f"x_{split}.h5", tmp_path / f"y_{split}.h5"
    hmu._split_paths = fake_paths
    try:
        hmu.write_split("train", [(images, classes)], 4, tmp_path)
    finally:
        hmu._split_paths = orig_paths
    with h5py.File(tmp_path / "x_train.h5", "r") as fx:
        assert fx["x"].shape == (4, TILE, TILE, 3)
        np.testing.assert_array_equal(fx["x"][0], images[0])
    with h5py.File(tmp_path / "y_train.h5", "r") as fy:
        np.testing.assert_array_equal(fy["y"][:], [1, 0, 1, 0])
        np.testing.assert_array_equal(fy["cls"][:], classes)
        assert fy.attrs["classes"] == ",".join(CLASSES)


def test_write_split_rejects_overcount(tmp_path):
    import training.download_hmu_gc as hmu
    orig_paths = hmu._split_paths
    hmu._split_paths = lambda split, data_dir: (tmp_path / "x.h5", tmp_path / "y.h5")
    try:
        with pytest.raises(RuntimeError, match="more than"):
            hmu.write_split("train", [(np.zeros((3, TILE, TILE, 3), np.uint8),
                                       np.zeros(3, np.uint8))], 2, tmp_path)
    finally:
        hmu._split_paths = orig_paths
