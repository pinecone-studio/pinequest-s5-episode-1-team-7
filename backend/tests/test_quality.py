"""Tests for the capture-time blur gate (TDD 8.1) - see app/quality.py."""
import math

import cv2
import numpy as np
import pytest

from app import config, ingest, quality
from helpers import make_jpeg


def _textured_jpeg(size=(256, 256)) -> bytes:
    rng = np.random.default_rng(7)
    img = rng.integers(0, 256, (*size, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def _tissue(size=1024, seed=7):
    """Correlated texture (closer to cells than white noise) at `size` px square."""
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 256, (size, size, 3), dtype=np.uint8)
    return cv2.GaussianBlur(img, (3, 3), 0.8)


def _encode(img) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def _blurred(data: bytes) -> bytes:
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    blurred = cv2.GaussianBlur(img, (21, 21), 5.0)
    ok, buf = cv2.imencode(".jpg", blurred, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def test_sharp_scores_above_blurred():
    sharp, blurred = _textured_jpeg(), _blurred(_textured_jpeg())
    assert quality.sharpness_score(sharp) > 100 > quality.sharpness_score(blurred)


def test_undecodable_bytes_rejected():
    with pytest.raises(ValueError):
        quality.sharpness_score(b"hello world")


def test_gate_disabled_by_default(env):
    assert config.SHARPNESS_THRESHOLD <= 0
    assert quality.check_sharpness(make_jpeg(), 0) >= 0  # solid colour scores ~0 but passes


def test_blurry_image_rejected_when_gate_enabled(env, monkeypatch):
    monkeypatch.setattr(config, "SHARPNESS_THRESHOLD", 100)
    sharp, blurred = _textured_jpeg(), _blurred(_textured_jpeg())
    assert ingest.ingest_bytes(sharp, "P-1") > 0
    with pytest.raises(ValueError, match="too blurry"):
        ingest.ingest_bytes(blurred, "P-1")


def test_blur_rejection_saves_nothing(env, monkeypatch):
    from app import db, queue
    monkeypatch.setattr(config, "SHARPNESS_THRESHOLD", 100)
    with pytest.raises(ValueError, match="too blurry"):
        ingest.ingest_bytes(_blurred(_textured_jpeg()), "P-1")
    with db.session() as conn:
        assert queue.list_all(conn) == []
    assert list((env / "images").iterdir()) == []


def test_blurry_upload_gets_422(env, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app import pipeline, engine_adapter
    from app.main import app
    monkeypatch.setattr(config, "SHARPNESS_THRESHOLD", 100)
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    with TestClient(app) as client:
        r = client.post("/ingest", files={"file": ("b.jpg", _blurred(_textured_jpeg()), "image/jpeg")})
        assert r.status_code == 422 and "blurry" in r.json()["detail"]
        r = client.post("/ingest", files={"file": ("s.jpg", _textured_jpeg(), "image/jpeg")})
        assert r.status_code == 202


def test_score_is_stable_across_capture_resolutions():
    """Same content captured at 1024 vs 2048 px must score nearly the same (issue #40):
    without the working-size normalisation raw scores grow ~4x per 2x edge."""
    base = _tissue(1024)
    hires = cv2.resize(base, (2048, 2048), interpolation=cv2.INTER_CUBIC)
    s1 = quality.sharpness_score(_encode(base))
    s2 = quality.sharpness_score(_encode(hires))
    assert s1 > 0 and max(s1, s2) / min(s1, s2) < 1.5


def test_large_blurry_capture_scores_low():
    blurred = cv2.GaussianBlur(_tissue(2048, seed=11), (21, 21), 5.0)
    assert quality.sharpness_score(_encode(blurred)) < 10


def test_suggest_threshold_is_geometric_mean():
    threshold, separable = quality.suggest_threshold([10.0, 20.0], [1.0, 2.0])
    assert separable and threshold == pytest.approx(math.sqrt(10.0 * 2.0))


def test_suggest_threshold_reports_overlap():
    _, separable = quality.suggest_threshold([1.0, 50.0], [5.0, 6.0])
    assert not separable


def test_suggest_threshold_needs_both_sets():
    with pytest.raises(ValueError):
        quality.suggest_threshold([], [1.0])


def _write_calibration_set(root, n_sharp=3, n_blurry=3, seed=21):
    sharp_d, blurry_d = root / "sharp", root / "blurry"
    sharp_d.mkdir()
    blurry_d.mkdir()
    for i in range(n_sharp):
        (sharp_d / f"s{i}.jpg").write_bytes(_encode(_tissue(512, seed=seed + i)))
    for i in range(n_blurry):
        tissue = _tissue(512, seed=seed + 100 + i)
        (blurry_d / f"b{i}.jpg").write_bytes(
            _encode(cv2.GaussianBlur(tissue, (21, 21), 5.0)))
    return sharp_d, blurry_d


def test_calibration_cli_suggests_threshold(tmp_path, capsys):
    sharp_d, blurry_d = _write_calibration_set(tmp_path)
    assert quality.main([str(sharp_d), str(blurry_d)]) == 0
    out = capsys.readouterr().out
    assert "TRIAGE_SHARPNESS=" in out and "sharp" in out and "blurry" in out


def test_calibration_cli_reports_overlap(tmp_path, capsys):
    d = tmp_path / "same"
    d.mkdir()
    (d / "a.jpg").write_bytes(_encode(_tissue(256)))
    assert quality.main([str(d), str(d)]) == 1
    assert "overlap" in capsys.readouterr().err


def test_calibration_cli_rejects_bad_input(tmp_path, capsys):
    assert quality.main([str(tmp_path / "nope"), str(tmp_path)]) == 2
    empty1, empty2 = tmp_path / "e1", tmp_path / "e2"
    empty1.mkdir()
    empty2.mkdir()
    assert quality.main([str(empty1), str(empty2)]) == 2


def test_score_dir_skips_undecodable_files(tmp_path, capsys):
    d = tmp_path / "mixed"
    d.mkdir()
    (d / "ok.jpg").write_bytes(_encode(_tissue(128)))
    (d / "notes.txt").write_bytes(b"not an image")
    scores = quality.score_dir(d)
    assert list(scores) == ["ok.jpg"] and scores["ok.jpg"] > 0
    assert "skipping" in capsys.readouterr().err


def _same_slide_two_objectives(seed=41):
    """Same field of view as a 40x capture (um 0.42, 2048 px) and a 10x one
    (um 1.68, 512 px), sharp and with the same physical defocus (~2 µm)."""
    fov = _tissue(1024, seed=seed)
    hi = cv2.resize(fov, (2048, 2048), interpolation=cv2.INTER_CUBIC)
    lo = cv2.resize(fov, (512, 512), interpolation=cv2.INTER_AREA)
    return {
        "sharp40": _encode(hi), "sharp10": _encode(lo),
        "blur40": _encode(cv2.GaussianBlur(hi, (0, 0), 4.8)),
        "blur10": _encode(cv2.GaussianBlur(lo, (0, 0), 1.2)),
    }


def test_same_defocus_scores_same_at_any_objective():
    """Model-scale scoring (issue #35) makes one threshold work at any
    objective; native scoring does not transfer between 40x and 10x."""
    cap = _same_slide_two_objectives()
    native = (quality.sharpness_score(cap["blur40"]), quality.sharpness_score(cap["blur10"]))
    assert max(native) / min(native) > 2
    scaled = (quality.sharpness_score(cap["blur40"], 0.42), quality.sharpness_score(cap["blur10"], 1.68))
    assert max(scaled) / min(scaled) < 1.5


def test_bad_um_per_px_rejected():
    for bad in (0, -1.0, float("nan"), float("inf"), "wide"):
        with pytest.raises(ValueError):
            quality.sharpness_score(_textured_jpeg(), bad)


def test_gate_uses_slide_scale(env, monkeypatch):
    """Ingested with a setup, the gate scores at model scale: one threshold
    rejects the same defocus at 40x and at 10x."""
    from app import db, setups
    monkeypatch.setattr(config, "SHARPNESS_THRESHOLD", 10)
    with db.session() as conn:
        sid = setups.create_setup(conn, "scope", 0.42, "40x")
    cap = _same_slide_two_objectives()
    assert ingest.ingest_bytes(cap["sharp40"], None, "Routine", sid, "40x") > 0
    assert ingest.ingest_bytes(cap["sharp10"], None, "Routine", sid, "10x") > 0
    with pytest.raises(ValueError, match="too blurry"):
        ingest.ingest_bytes(cap["blur40"], None, "Routine", sid, "40x")
    with pytest.raises(ValueError, match="too blurry"):
        ingest.ingest_bytes(cap["blur10"], None, "Routine", sid, "10x")


def test_calibration_cli_accepts_um_per_px(tmp_path, capsys):
    sharp_d, blurry_d = _write_calibration_set(tmp_path)
    assert quality.main([str(sharp_d), str(blurry_d), "--um-per-px", "0.84"]) == 0
    assert "TRIAGE_SHARPNESS=" in capsys.readouterr().out


def test_calibration_cli_rejects_bad_um(tmp_path):
    sharp_d, blurry_d = _write_calibration_set(tmp_path)
    with pytest.raises(SystemExit) as exc:
        quality.main([str(sharp_d), str(blurry_d), "--um-per-px", "0"])
    assert exc.value.code == 2
