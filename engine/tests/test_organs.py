"""Tests for one model per organ (pipeline/organs.py, issue #53)."""
import json
import os
import shutil

import cv2
import numpy as np
import pytest

from pipeline import analyze_slide, available_organs, model_info, organs
from pipeline.organs import DEFAULT_ORGAN, OrganModel, get_organ

TISSUE = (200, 120, 180)


@pytest.fixture
def colon(tmp_path, monkeypatch, tiny_model):
    """A second organ with its own folder, scale and thresholds (red at 0: every slide is red)."""
    folder = tmp_path / "colon"
    folder.mkdir()
    shutil.copy(tiny_model, folder / organs.MODEL_FILE)
    (folder / organs.CARD_FILE).write_text(json.dumps({"name": "colon test card"}))
    spec = OrganModel("colon", folder, um_per_px=0.5, red=0.0, yellow=0.0)
    monkeypatch.setitem(organs.ORGANS, "colon", spec)
    return spec


@pytest.fixture
def slide(tmp_path):
    path = tmp_path / "slide.png"
    cv2.imwrite(str(path), np.full((448, 448, 3), TISSUE[::-1], dtype=np.uint8))
    yield str(path)


def _analyze(*args, **kwargs):
    result = analyze_slide(*args, **kwargs)
    os.remove(result["heatmap_path"])
    return result


def test_get_organ_defaults_and_rejects_unknown():
    assert get_organ().organ == get_organ(None).organ == DEFAULT_ORGAN
    with pytest.raises(ValueError, match="no AI model for organ 'liver'"):
        get_organ("liver")


def test_analyze_slide_uses_the_organs_model_settings(colon, slide):
    lymph = _analyze(slide, um_per_px=0.42)
    result = _analyze(slide, um_per_px=0.42, organ="colon")

    assert result["organ"] == "colon"
    assert result["risk_flag"] == "red"  # the colon thresholds, not the lymph-node ones
    # Resized by 0.42 / 0.5 for the colon model: 448 -> 376 px, so one full tile plus two
    # 152 px edge tiles (68% tissue, kept) and a 152 x 152 corner (46%, dropped).
    assert lymph["num_patches"] == 4
    assert result["num_patches"] == 3


def test_analyze_slide_rejects_unknown_organ(slide):
    with pytest.raises(ValueError, match="no AI model for organ"):
        analyze_slide(slide, organ="liver")


def test_missing_organ_model_fails_loudly(colon, slide):
    (colon.folder / organs.MODEL_FILE).unlink()
    with pytest.raises(FileNotFoundError, match="AI model not found"):
        analyze_slide(slide, organ="colon")


def test_triage_model_path_only_replaces_the_default_organ(colon, tiny_model):
    assert get_organ().model_path == tiny_model  # conftest sets TRIAGE_MODEL_PATH
    assert colon.model_path == colon.folder / organs.MODEL_FILE


def test_available_organs_lists_only_organs_with_a_model(colon, monkeypatch, tmp_path):
    assert available_organs() == [DEFAULT_ORGAN, "colon"]
    monkeypatch.setitem(organs.ORGANS, "stomach", OrganModel("stomach", tmp_path / "none", 0.5, 0.8, 0.7))
    assert "stomach" not in available_organs()


def test_model_info_per_organ(colon):
    info = model_info("colon")
    assert info["organ"] == "colon"
    assert info["card"] == {"name": "colon test card"}
    assert info["file"]["exists"] is True


def test_model_info_never_raises_for_unknown_organ():
    info = model_info("liver")
    assert info["organ"] == "liver"
    assert info["card"] is None
    assert info["file"]["exists"] is False
    assert info["provider"] is None
