import pytest

from app.capture.source import CaptureManager


def test_snapshot_requires_started_capture():
    with pytest.raises(RuntimeError):
        CaptureManager().snapshot_jpeg()


@pytest.mark.parametrize("source", ["ftp://x", "usb", "uvc:abc", ""])
def test_invalid_sources_rejected(source):
    with pytest.raises(ValueError):
        CaptureManager().start(source)


def test_unreachable_source_raises_connection_error():
    with pytest.raises(ConnectionError):
        CaptureManager().start("uvc:99")  # no such camera


def test_status_when_idle():
    assert CaptureManager().status == {"active": False, "source": None}


def test_fake_camera_snapshot(monkeypatch):
    import numpy as np

    class FakeCap:
        def __init__(self): self.released = False
        def isOpened(self): return True
        def set(self, *a): return True
        def read(self): return True, np.full((48, 64, 3), 128, dtype=np.uint8)
        def release(self): self.released = True

    fake = FakeCap()
    monkeypatch.setattr(CaptureManager, "_open", staticmethod(lambda source: fake))
    mgr = CaptureManager()
    mgr.start("uvc:0")
    assert mgr.status == {"active": True, "source": "uvc:0"}
    jpeg = mgr.snapshot_jpeg()
    assert jpeg[:2] == b"\xff\xd8"  # JPEG magic
    mgr.stop()
    assert fake.released and mgr.status["active"] is False


def test_snapshot_endpoint_end_to_end(env, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import numpy as np
    from fastapi.testclient import TestClient
    from app import engine_adapter, pipeline
    from app.capture.source import capture_manager
    from app.main import app

    class FakeCap:
        def isOpened(self): return True
        def set(self, *a): return True
        def read(self): return True, np.full((48, 64, 3), (160, 40, 120), dtype=np.uint8)
        def release(self): pass

    monkeypatch.setattr(CaptureManager, "_open", staticmethod(lambda source: FakeCap()))
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    with TestClient(app) as client:
        assert client.post("/capture/snapshot", json={}).status_code == 409  # not started
        assert client.post("/capture/start", json={"source": "ftp://x"}).status_code == 422
        assert client.post("/capture/start", json={"source": "uvc:0"}).json()["active"] is True
        r = client.post("/capture/snapshot", json={"patient_id": "P-9", "indication": "Urgent"})
        assert r.status_code == 202
        slide = client.get(f"/slides/{r.json()['id']}").json()
        assert slide["state"] == "queued" and slide["indication"] == "Urgent"
        assert client.post("/capture/stop").json()["active"] is False
    capture_manager.stop()
