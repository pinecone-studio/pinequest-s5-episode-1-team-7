"""API tests - need fastapi + httpx (pip install -r requirements.txt)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from helpers import make_jpeg  # noqa: E402

PALE, STAINED = (250, 250, 250), (120, 20, 160)


@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    """Keep API tests independent of Member 1's real model."""
    from app import engine_adapter, pipeline
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)


def _ingest(client, color=STAINED, **data):
    return client.post("/ingest", files={"file": ("s.jpg", make_jpeg(color), "image/jpeg")}, data=data)


def test_health(env):
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_ingest_to_sorted_queue(env):
    with TestClient(app) as client:
        for color in (PALE, STAINED):
            r = _ingest(client, color, patient_id="P-1", indication="Routine")
            assert r.status_code == 202 and r.json()["state"] == "new"
        queue = client.get("/queue").json()
        scores = [s["risk_score"] for s in queue]
        assert len(scores) == 2 and scores == sorted(scores, reverse=True)
        assert all(s["state"] == "queued" and s["has_heatmap"] for s in queue)
        assert "patient_id" not in queue[0] and "P-1" not in str(queue)


def test_ingest_rejects_bad_input(env):
    with TestClient(app) as client:
        assert client.post("/ingest", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 422
        assert _ingest(client, indication="Whenever").status_code == 422
        assert client.post("/ingest").status_code == 422  # no file


def test_slide_files_and_events(env):
    with TestClient(app) as client:
        sid = _ingest(client).json()["id"]
        assert client.get(f"/slides/{sid}/image").status_code == 200
        heat = client.get(f"/slides/{sid}/heatmap")
        assert heat.status_code == 200 and heat.headers["content-type"] == "image/png"
        states = [e["to_state"] for e in client.get(f"/slides/{sid}/events").json()]
        assert states == ["new", "image_processing", "ai_running", "scored", "queued"]


def test_not_found(env):
    with TestClient(app) as client:
        for path in ("/slides/999", "/slides/999/image", "/slides/999/heatmap", "/slides/999/events"):
            assert client.get(path).status_code == 404
        assert client.post("/slides/999/open").status_code == 404
        assert client.post("/slides/999/action", json={"action": "mark_benign"}).status_code == 404


def test_open_then_archive(env):
    with TestClient(app) as client:
        sid = _ingest(client).json()["id"]
        assert client.post(f"/slides/{sid}/open").json()["state"] == "under_review"
        assert client.get("/queue").json() == []
        r = client.post(f"/slides/{sid}/action", json={"action": "mark_benign"})
        assert r.json()["state"] == "archived" and r.json()["decision"] == "mark_benign"
        assert client.post(f"/slides/{sid}/open").status_code == 409


def test_action_before_open_is_conflict(env):
    with TestClient(app) as client:
        sid = _ingest(client).json()["id"]
        assert client.post(f"/slides/{sid}/action", json={"action": "mark_benign"}).status_code == 409


def test_reassign_priority_reorders_queue(env):
    with TestClient(app) as client:
        high = _ingest(client, STAINED).json()["id"]
        low = _ingest(client, PALE).json()["id"]
        assert [s["id"] for s in client.get("/queue").json()] == [high, low]
        r = client.post(f"/slides/{low}/action", json={"action": "reassign_priority", "priority": 1.0})
        assert r.status_code == 200
        assert client.get("/queue").json()[0]["id"] == low
        bad = client.post(f"/slides/{low}/action", json={"action": "reassign_priority", "priority": 7})
        assert bad.status_code == 422


def test_retry_failed_slide(env, monkeypatch):
    from app import pipeline
    calls = {"n": 0}

    def flaky(_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return {"score": 0.5}
    monkeypatch.setattr(pipeline, "load_engine", lambda: flaky)
    with TestClient(app) as client:
        sid = _ingest(client).json()["id"]
        failed = client.get(f"/slides/{sid}").json()
        assert failed["state"] == "failed" and "boom" in failed["error"]
        assert client.get("/queue").json() == []
        assert client.post(f"/slides/{sid}/retry").status_code == 202
        assert client.get(f"/slides/{sid}").json()["state"] == "queued"
        assert client.post(f"/slides/{sid}/retry").status_code == 409  # only FAILED slides


def test_sort_param_validation(env):
    with TestClient(app) as client:
        assert client.get("/queue?sort=time").status_code == 200
        assert client.get("/queue?sort=banana").status_code == 422
