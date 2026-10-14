"""Tests for pipeline.model_info() and the committed model card (About the AI)."""
import hashlib
import json
from pathlib import Path

from pipeline import model_info
from pipeline.scoring import RED_THRESHOLD, TOP_K, W_MAX, YELLOW_THRESHOLD

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
RESULTS = Path(__file__).resolve().parents[1] / "training" / "results"


def _card():
    return json.loads((MODEL_DIR / "model_card.json").read_text())


def test_model_info_reports_live_file_and_provider():
    info = model_info()
    assert set(info) == {"organ", "card", "file", "provider"}
    assert info["organ"] == "lymph_node"
    assert set(info["file"]) == {"path", "name", "exists", "sha256", "matches_card"}
    # Tests run against the tiny fixture model (conftest), not the shipped one.
    assert info["file"]["exists"] is True
    assert info["file"]["name"] == "tiny_model.onnx"
    assert info["file"]["matches_card"] is False
    assert info["provider"] == "CPUExecutionProvider"
    assert info["card"]["version"] == "model_fp32.onnx"


def test_model_info_never_raises_without_model(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIAGE_MODEL_PATH", str(tmp_path / "missing.onnx"))
    info = model_info()  # must not raise: the About page works even when broken
    assert info["file"] == {"path": str(tmp_path / "missing.onnx"), "name": "missing.onnx",
                            "exists": False, "sha256": None, "matches_card": False}
    assert info["provider"] is None
    assert info["card"] is not None


def test_committed_card_matches_evidence():
    """The card's numbers are pinned to the evidence files (no onnx package needed)."""
    card = _card()
    for section in ("name", "version", "file", "architecture", "provenance", "runtime",
                    "patch_metrics", "slide_metrics", "plism", "comparison", "limitations", "generated"):
        assert section in card, f"card section missing: {section}"

    shipped = MODEL_DIR / "model_fp32.onnx"
    digest = hashlib.sha256()
    with open(shipped, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    assert card["file"]["sha256"] == digest.hexdigest()

    kd = json.loads((RESULTS / "pcam_mobilenet_v3_small_224_kd-hibou.json").read_text())
    assert card["patch_metrics"]["auc"] == round(kd["test"]["auc"], 4)
    assert card["provenance"]["distilled_from"].startswith(kd["teacher"])

    scoring = json.loads((RESULTS / "slide_scoring.json").read_text())
    assert scoring["model"] == "model_fp32.onnx"
    assert card["slide_metrics"]["thresholds"] == {"red": RED_THRESHOLD, "yellow": YELLOW_THRESHOLD}
    assert (W_MAX, TOP_K) == (scoring["chosen"]["w_max"], scoring["chosen"]["top_k"])
    assert card["slide_metrics"]["normal_slides"] == scoring["test"]["normal_slides"]


def test_committed_colon_card_matches_its_model_and_settings():
    """Each organ's card describes its own committed model and the settings in pipeline/organs.py."""
    from pipeline.organs import get_organ

    colon = get_organ("colon")
    card = json.loads(colon.card_path.read_text(encoding="utf-8"))
    assert card["organ"] == "colon"
    digest = hashlib.sha256(colon.model_path.read_bytes()).hexdigest()
    assert card["file"]["sha256"] == digest
    assert card["architecture"]["input_scale_um_per_px"] == colon.um_per_px
    assert card["slide_metrics"]["thresholds"] == {"red": colon.red, "yellow": colon.yellow}

    scoring = json.loads((RESULTS / "slide_scoring_colon.json").read_text())
    assert (colon.w_max, colon.top_k) == (scoring["chosen"]["w_max"], scoring["chosen"]["top_k"])
    assert (round(scoring["chosen"]["red"], 2), round(scoring["chosen"]["yellow"], 2)) == (colon.red, colon.yellow)
