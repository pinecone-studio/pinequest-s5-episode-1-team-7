"""Tests for the model card endpoint and per-slide model audit (About the AI)."""
import pytest

from app import db, engine_adapter, ingest, pipeline, queue
from helpers import make_jpeg


def _api():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_model_endpoint_serves_card_and_live_status(env):
    from app.main import app  # noqa: F401 (import for TestClient lifespan)
    with _api() as client:
        r = client.get("/model")
        assert r.status_code == 200
        info = r.json()
        assert info["card"]["version"] == "model_fp32.onnx"
        assert info["card"]["patch_metrics"]["auc"] == pytest.approx(0.9687)
        assert info["file"]["name"] == "model_fp32.onnx"
        assert info["file"]["exists"] is True and info["file"]["matches_card"] is True
        assert info["provider"] == "CPUExecutionProvider"


def test_model_endpoint_503_without_engine(env, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ENGINE_ENTRYPOINT", "no.such.module:missing")
    with _api() as client:
        assert client.get("/model").status_code == 503


def test_model_endpoint_503_for_engine_without_model_info(env, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ENGINE_ENTRYPOINT", "app.queue:get_slide")
    with _api() as client:
        assert client.get("/model").status_code == 503


def test_scored_slide_records_model(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    slide_id = ingest.ingest_bytes(make_jpeg(), None)
    pipeline.process_slide(slide_id)
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["state"] == "queued"
    assert row["model_name"] == "model_fp32.onnx"
    assert row["model_sha256"] == engine_adapter.get_model_info()["file"]["sha256"]


def test_stub_scored_slide_is_labelled_stub(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    monkeypatch.setattr(pipeline, "get_model_info", lambda: None)
    slide_id = ingest.ingest_bytes(make_jpeg(), None)
    pipeline.process_slide(slide_id)
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert (row["model_name"], row["model_sha256"]) == ("stub", None)


def test_slide_api_exposes_model(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    monkeypatch.setattr(pipeline, "get_model_info", lambda: None)
    with _api() as client:
        sid = client.post("/ingest", files={"file": ("s.jpg", make_jpeg(), "image/jpeg")}).json()["id"]
        slide = client.get(f"/slides/{sid}").json()
        assert slide["model_name"] == "stub" and slide["model_sha256"] is None


def test_model_columns_migrated(env):
    with db.session() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(slides)")}
    assert {"model_name", "model_sha256"} <= cols
