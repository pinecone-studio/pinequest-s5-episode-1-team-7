"""Tests for the capture-time blur gate (TDD 8.1) - see app/quality.py."""
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
