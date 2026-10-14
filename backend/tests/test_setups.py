"""Tests for magnification calibration: setup profiles, um_per_px flow, engine kwarg (issue #35)."""
import pytest

from app import config, db, ingest, pipeline, queue, setups
from helpers import make_jpeg


def _setup(conn, name="scope-A", um=0.5, calib="40x"):
    return setups.create_setup(conn, name, um, calib, "4000x3000")


def test_parse_magnification():
    assert setups.parse_magnification("40x") == 40.0
    assert setups.parse_magnification(" 10 X ") == 10.0
    for bad in ("", "40", "x", "0x", "-10x", "high"):
        with pytest.raises(ValueError):
            setups.parse_magnification(bad)


def test_um_per_px_scales_with_objective(env):
    with db.session() as conn:
        sid = _setup(conn)
        assert setups.um_per_px_for(conn, sid) == 0.5  # calibration objective
        assert setups.um_per_px_for(conn, sid, "40x") == pytest.approx(0.5)
        assert setups.um_per_px_for(conn, sid, "10x") == pytest.approx(2.0)
        assert setups.um_per_px_for(conn, sid, "20x") == pytest.approx(1.0)
        with pytest.raises(KeyError):
            setups.um_per_px_for(conn, 999, "10x")
        with pytest.raises(ValueError):
            setups.um_per_px_for(conn, sid, "wide")


def test_setup_validation(env):
    with db.session() as conn:
        for bad in [dict(name="", um=0.5, calib="40x"), dict(name="s", um=0, calib="40x"),
                    dict(name="s", um=-1, calib="40x"), dict(name="s", um=float("nan"), calib="40x"),
                    dict(name="s", um=0.5, calib="wide")]:
            with pytest.raises(ValueError):
                setups.create_setup(conn, bad["name"], bad["um"], bad["calib"])
        _setup(conn, name="dup")
        with pytest.raises(ValueError, match="already exists"):
            setups.create_setup(conn, "dup", 0.5, "40x")


def test_setup_delete_guards(env):
    with db.session() as conn:
        sid = _setup(conn)
        setups.delete_setup(conn, sid)
        assert setups.get_setup(conn, sid) is None
        with pytest.raises(KeyError):
            setups.delete_setup(conn, sid)
        used = _setup(conn, name="used")
        slide = queue.create_slide(conn, "h", "Routine", "/tmp/x.jpg", used, "10x", 2.0)
        assert slide > 0
        with pytest.raises(ValueError, match="still used"):
            setups.delete_setup(conn, used)


def test_init_db_migrates_old_databases(tmp_path):
    """A database from before #35 (no setups table, narrow slides) gains the columns, keeping rows."""
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE slides (id INTEGER PRIMARY KEY AUTOINCREMENT, local_hash TEXT NOT NULL,"
                 " indication TEXT NOT NULL DEFAULT 'Routine', state TEXT NOT NULL, image_path TEXT NOT NULL)")
    conn.execute("INSERT INTO slides (local_hash, state, image_path) VALUES ('h', 'new', '/tmp/x.jpg')")
    conn.commit()
    conn.close()
    db.init_db(path)
    with db.session(path) as conn:
        row = queue.get_slide(conn, 1)
        assert row["local_hash"] == "h" and row["um_per_px"] is None and row["scale_warning"] is None
        assert setups.create_setup(conn, "s", 0.5, "40x") > 0


def test_ingest_with_setup_stores_scale(env):
    with db.session() as conn:
        sid = _setup(conn)
    slide_id = ingest.ingest_bytes(make_jpeg(), "P-1", "Routine", sid, "10x")
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["setup_id"] == sid and row["objective"] == "10x" and row["um_per_px"] == pytest.approx(2.0)


def test_ingest_rejects_bad_scale_input(env):
    with db.session() as conn:
        sid = _setup(conn)
    with pytest.raises(ValueError, match="needs a setup_id"):
        ingest.ingest_bytes(make_jpeg(), None, "Routine", None, "10x")
    with pytest.raises(ValueError, match="unknown setup_id"):
        ingest.ingest_bytes(make_jpeg(), None, "Routine", 999, "10x")
    with pytest.raises(ValueError, match="objective"):
        ingest.ingest_bytes(make_jpeg(), None, "Routine", sid, "wide")
    with db.session() as conn:
        assert queue.list_all(conn) == []
    assert list((env / "images").iterdir()) == []


def test_engine_receives_um_per_px(env, monkeypatch):
    seen = {}

    def spy(path, um_per_px=None):
        seen["um"] = um_per_px
        return {"score": 0.5, "um_per_px_used": um_per_px}
    monkeypatch.setattr(pipeline, "load_engine", lambda: spy)
    with db.session() as conn:
        sid = _setup(conn)
    slide_id = ingest.ingest_bytes(make_jpeg(), None, "Routine", sid, "20x")
    pipeline.process_slide(slide_id)
    assert seen["um"] == pytest.approx(1.0)
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["state"] == "queued" and row["um_per_px"] == pytest.approx(1.0)


def test_old_engine_without_um_param_still_works(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: (lambda p: {"score": 0.4}))
    with db.session() as conn:
        sid = _setup(conn)
    slide_id = ingest.ingest_bytes(make_jpeg(), None, "Routine", sid, "40x")
    pipeline.process_slide(slide_id)  # must not raise TypeError
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["state"] == "queued" and row["um_per_px"] == pytest.approx(0.5)


def test_scale_warning_is_stored(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine",
                        lambda: (lambda p, um_per_px=None: {"score": 0.3, "scale_warning": "no_scale_info"}))
    slide_id = ingest.ingest_bytes(make_jpeg(), None)
    pipeline.process_slide(slide_id)
    with db.session() as conn:
        row = queue.get_slide(conn, slide_id)
    assert row["scale_warning"] == "no_scale_info" and row["um_per_px"] is None


def test_setups_api(env):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/setups").json() == []
        r = client.post("/setups", json={"name": "Scope A", "um_per_px": 0.5,
                                         "calibration_objective": "40x", "phone_resolution": "4000x3000"})
        assert r.status_code == 201
        created = r.json()
        assert created["um_per_px"] == 0.5 and created["calibration_objective"] == "40x"
        assert client.post("/setups", json={"name": "Scope A", "um_per_px": 0.5,
                                            "calibration_objective": "40x"}).status_code == 422
        assert client.post("/setups", json={"name": "bad", "um_per_px": 0.5,
                                            "calibration_objective": "wide"}).status_code == 422
        assert client.post("/setups", json={"name": "bad", "um_per_px": -1,
                                            "calibration_objective": "40x"}).status_code == 422
        assert [s["name"] for s in client.get("/setups").json()] == ["Scope A"]
        assert client.get(f"/setups/{created['id']}").json()["name"] == "Scope A"
        assert client.get("/setups/999").status_code == 404
        assert client.delete(f"/setups/{created['id']}").status_code == 204
        assert client.delete(f"/setups/{created['id']}").status_code == 404


def test_delete_setup_in_use_is_conflict(env):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        sid = client.post("/setups", json={"name": "S", "um_per_px": 0.5,
                                           "calibration_objective": "40x"}).json()["id"]
        assert client.post("/ingest", files={"file": ("s.jpg", make_jpeg(), "image/jpeg")},
                           data={"setup_id": str(sid), "objective": "10x"}).status_code == 202
        assert client.delete(f"/setups/{sid}").status_code == 409


def test_ingest_api_with_setup(env, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app import engine_adapter
    from app.main import app
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    with TestClient(app) as client:
        sid = client.post("/setups", json={"name": "S", "um_per_px": 0.5,
                                           "calibration_objective": "40x"}).json()["id"]
        r = client.post("/ingest", files={"file": ("s.jpg", make_jpeg(), "image/jpeg")},
                        data={"setup_id": str(sid), "objective": "10x"})
        assert r.status_code == 202
        slide = client.get(f"/slides/{r.json()['id']}").json()
        assert slide["setup_id"] == sid and slide["objective"] == "10x"
        assert slide["um_per_px"] == pytest.approx(2.0)
        assert slide["scale_warning"] is None  # stub got um_per_px, so no warning
        bad = client.post("/ingest", files={"file": ("s.jpg", make_jpeg(), "image/jpeg")},
                          data={"objective": "10x"})
        assert bad.status_code == 422
        bad = client.post("/ingest", files={"file": ("s.jpg", make_jpeg(), "image/jpeg")},
                          data={"setup_id": "999"})
        assert bad.status_code == 422


def test_snapshot_api_with_setup(env, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import numpy as np
    from fastapi.testclient import TestClient
    from app import engine_adapter
    from app.capture.source import CaptureManager, capture_manager
    from app.main import app

    class FakeCap:
        def isOpened(self): return True
        def set(self, *a): return True
        def read(self): return True, np.full((48, 64, 3), (160, 40, 120), dtype=np.uint8)
        def release(self): pass

    monkeypatch.setattr(CaptureManager, "_open", staticmethod(lambda source: FakeCap()))
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    with TestClient(app) as client:
        sid = client.post("/setups", json={"name": "S", "um_per_px": 1.0,
                                           "calibration_objective": "10x"}).json()["id"]
        assert client.post("/capture/start", json={"source": "uvc:0"}).json()["active"] is True
        r = client.post("/capture/snapshot", json={"setup_id": sid, "objective": "40x"})
        assert r.status_code == 202
        slide = client.get(f"/slides/{r.json()['id']}").json()
        assert slide["um_per_px"] == pytest.approx(0.25)
        assert client.post("/capture/stop").json()["active"] is False
    capture_manager.stop()
