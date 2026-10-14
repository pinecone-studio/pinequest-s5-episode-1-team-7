import os

import cv2
import numpy as np
import pytest

from pipeline import analyze_slide

WHITE = (245, 245, 245)
TISSUE = (200, 120, 180)


def write_image(path, rgb):
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return str(path)


@pytest.fixture
def result_cleanup():
    """Delete the temp heatmaps analyze_slide creates."""
    paths = []
    yield paths
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def test_analyze_slide_scores_tissue_and_writes_heatmap(tmp_path, result_cleanup):
    image = np.full((300, 500, 3), WHITE, dtype=np.uint8)
    image[:, :224] = TISSUE  # left column of the 2x3 grid is tissue
    result = analyze_slide(write_image(tmp_path / "slide.png", image))
    result_cleanup.append(result["heatmap_path"])

    assert set(result) == {"score", "risk_flag", "heatmap_path", "num_patches", "inference_ms",
                            "um_per_px_used", "scale_warning"}
    assert result["um_per_px_used"] is None
    assert result["scale_warning"] == "no_scale_info"  # analysed at captured resolution
    assert result["risk_flag"] in {"red", "yellow", "green"}
    assert 0.0 < result["score"] <= 1.0
    assert result["num_patches"] == 1  # bottom-left tile is only 76/224 tissue -> dropped
    heatmap = cv2.imread(result["heatmap_path"], cv2.IMREAD_UNCHANGED)
    assert heatmap.shape == (300, 500, 4)
    assert result["inference_ms"] >= 0


def test_analyze_slide_blank_image_scores_zero(tmp_path, result_cleanup):
    image = np.full((448, 448, 3), WHITE, dtype=np.uint8)
    result = analyze_slide(write_image(tmp_path / "blank.png", image))
    result_cleanup.append(result["heatmap_path"])

    assert result["score"] == 0.0
    assert result["num_patches"] == 0
    assert (cv2.imread(result["heatmap_path"], cv2.IMREAD_UNCHANGED)[..., 3] == 0).all()


def test_analyze_slide_rejects_unreadable_file(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")

    with pytest.raises(ValueError):
        analyze_slide(str(path))


def test_analyze_slide_scores_tissue_higher_than_background(tmp_path, result_cleanup):
    pale = np.full((224, 448, 3), (230, 215, 225), dtype=np.uint8)
    pale[:, :224] = TISSUE
    result = analyze_slide(write_image(tmp_path / "slide.png", pale))
    result_cleanup.append(result["heatmap_path"])

    assert result["num_patches"] == 1  # the pale half is masked out as background
    assert result["score"] > 0.5  # tiny fixture model: stained tissue scores ~0.75


def test_analyze_slide_without_model_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGE_MODEL_PATH", str(tmp_path / "missing.onnx"))
    image = np.full((224, 224, 3), TISSUE, dtype=np.uint8)

    with pytest.raises(FileNotFoundError, match="AI model not found"):
        analyze_slide(write_image(tmp_path / "slide.png", image))


def test_analyze_slide_rescales_to_model_magnification(tmp_path, result_cleanup):
    """um_per_px=0.84 (2x the training scale) doubles a 448 px photo to 896 before
    tiling: 16 tissue patches instead of 4, but the heatmap stays photo-sized."""
    image = np.full((448, 448, 3), TISSUE, dtype=np.uint8)
    result = analyze_slide(write_image(tmp_path / "slide.png", image), um_per_px=0.84)
    result_cleanup.append(result["heatmap_path"])

    assert result["num_patches"] == 16
    assert result["um_per_px_used"] == 0.84
    assert result["scale_warning"] is None
    heatmap = cv2.imread(result["heatmap_path"], cv2.IMREAD_UNCHANGED)
    assert heatmap.shape == (448, 448, 4)


def test_analyze_slide_unity_scale_skips_resampling(tmp_path, result_cleanup):
    image = np.full((448, 448, 3), TISSUE, dtype=np.uint8)
    result = analyze_slide(write_image(tmp_path / "slide.png", image), um_per_px=0.42)
    result_cleanup.append(result["heatmap_path"])

    assert result["num_patches"] == 4  # same as analysing at captured resolution
    assert result["scale_warning"] is None


def test_analyze_slide_downscales_coarse_photos(tmp_path, result_cleanup):
    """um_per_px below training scale shrinks the photo (fewer, model-scale patches)."""
    image = np.full((448, 448, 3), TISSUE, dtype=np.uint8)
    result = analyze_slide(write_image(tmp_path / "slide.png", image), um_per_px=0.21)
    result_cleanup.append(result["heatmap_path"])

    assert result["num_patches"] == 1  # 224 px at model scale
    heatmap = cv2.imread(result["heatmap_path"], cv2.IMREAD_UNCHANGED)
    assert heatmap.shape == (448, 448, 4)


@pytest.mark.parametrize("bad", [0, -0.5, float("nan"), float("inf"), "wide"])
def test_analyze_slide_rejects_bad_um_per_px(tmp_path, bad):
    image = np.full((224, 224, 3), TISSUE, dtype=np.uint8)
    path = write_image(tmp_path / "slide.png", image)

    with pytest.raises(ValueError, match="um_per_px"):
        analyze_slide(path, um_per_px=bad)
