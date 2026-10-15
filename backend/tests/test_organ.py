"""Tests for per-organ models end to end (issue #53)."""
import pytest

from app import db, engine_adapter, ingest, pipeline, queue
from helpers import make_jpeg


def test_available_organs_lists_models(env):
    organs = engine_adapter.available_organs()
    assert organs[0] == engine_adapter.default_organ() == "lymph_node"
    assert "colon" in organs


def test_available_organs_empty_without_engine(env, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ENGINE_ENTRYPOINT", "no.such.module:missing")
    assert engine_adapter.available_organs() == []
    assert engine_adapter.default_organ() == "lymph_node"


def test_ingest_defaults_to_default_organ(env):
    slide_id = ingest.ingest_bytes(make_jpeg(), None)
    with db.session() as conn:
        assert queue.get_slide(conn, slide_id)["organ"] == "lymph_node"


def test_ingest_rejects_organ_without_model(env):
    with pytest.raises(ValueError, match="no AI model for organ"):
        ingest.ingest_bytes(make_jpeg(), None, "Routine", None, None, "lung")
    with db.session() as conn:
        assert queue.list_all(conn) == []
    assert list((env / "images").iterdir()) == []


def test_engine_receives_organ(env, monkeypatch):
    seen = {}

    def spy(path, um_per_px=None, organ=None):
        seen["organ"] = organ
        return {"score": 0.5, "organ": organ}
    monkeypatch.setattr(pipeline, "load_engine", lambda: spy)
    slide_id = ingest.ingest_bytes(make_jpeg(), None, "Routine", None, None, "colon")
    pipeline.process_slide(slide_id)
    assert seen["organ"] == "colon"
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["state"] == "queued" and row["organ"] == "colon"


def test_old_engine_without_organ_param_still_works(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: (lambda p: {"score": 0.4}))
    slide_id = ingest.ingest_bytes(make_jpeg(), None, "Routine", None, None, "colon")
    pipeline.process_slide(slide_id)  # must not raise TypeError
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["state"] == "queued" and row["organ"] == "colon"


def test_old_slide_without_organ_uses_default(env, monkeypatch):
    """Slides stored before organs existed score with the default organ's model."""
    seen = {}

    def spy(path, um_per_px=None, organ=None):
        seen["organ"] = organ
        return {"score": 0.5}
    monkeypatch.setattr(pipeline, "load_engine", lambda: spy)
    with db.session() as conn:
        slide_id = queue.create_slide(conn, "h", "Routine", "/tmp/x.jpg")
    pipeline.process_slide(slide_id)
    assert seen["organ"] == "lymph_node"


def test_organs_endpoint(env):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        organs = client.get("/organs").json()
        assert organs[0] == "lymph_node" and "colon" in organs


def test_model_endpoint_takes_organ(env):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/model?organ=colon").json()["organ"] == "colon"
        assert client.get("/model?organ=lung").status_code == 404
        assert client.get("/model").json()["organ"] == "lymph_node"


def test_queue_and_slides_filter_by_organ(env, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app import engine_adapter as ea
    from app.main import app
    monkeypatch.setattr(pipeline, "load_engine", lambda: ea._stub_analyze_slide)
    with TestClient(app) as client:
        lymph = client.post("/ingest", files={"file": ("a.jpg", make_jpeg(), "image/jpeg")}).json()["id"]
        colon = client.post("/ingest", files={"file": ("b.jpg", make_jpeg(), "image/jpeg")},
                            data={"organ": "colon"}).json()["id"]
        with db.session() as conn:  # a slide from before organs existed
            old = queue.create_slide(conn, "h", "Routine", "/tmp/x.jpg")
            queue.transition(conn, old, queue.SlideState.IMAGE_PROCESSING) if False else None
        assert client.get(f"/slides/{lymph}").json()["organ"] == "lymph_node"
        assert client.get(f"/slides/{colon}").json()["organ"] == "colon"
        with db.session() as conn:  # a queued slide from before organs existed (organ IS NULL)
            old = conn.execute(
                "INSERT INTO slides (local_hash, indication, state, image_path, risk_score)"
                " VALUES (?,?,?,?,?)", ("h", "Routine", "queued", "/tmp/x.jpg", 0.3)).lastrowid
        assert [s["id"] for s in client.get("/queue?organ=colon").json()] == [colon]
        assert sorted(s["id"] for s in client.get("/queue?organ=lymph_node").json()) == sorted([lymph, old])
        assert [s["id"] for s in client.get("/slides?organ=colon").json()] == [colon]
        assert client.get("/queue?organ=lung").json() == []


def test_organ_column_migrated(env):
    with db.session() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(slides)")}
    assert "organ" in cols
