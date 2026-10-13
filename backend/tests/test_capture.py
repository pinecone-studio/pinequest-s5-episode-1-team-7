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


class _MovingFakeCap:
    """A 1920x1080 fake camera whose frames differ, like a live feed."""

    def __init__(self):
        self.n = 0

    def isOpened(self): return True
    def set(self, *a): return True
    def grab(self): return True
    def release(self): pass

    def read(self):
        import numpy as np
        self.n += 1
        return True, np.full((1080, 1920, 3), self.n % 255, dtype=np.uint8)


def test_preview_frames_are_small_jpegs(monkeypatch):
    import cv2
    import numpy as np

    monkeypatch.setattr(CaptureManager, "_open", staticmethod(lambda source: _MovingFakeCap()))
    mgr = CaptureManager()
    with pytest.raises(RuntimeError):
        mgr.preview_jpeg()  # not started
    mgr.start("uvc:0")
    jpeg = mgr.preview_jpeg()
    frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert frame.shape[:2] == (540, 960)  # longest side capped at 960
    assert len(jpeg) < len(mgr.snapshot_jpeg())  # lighter than a full-resolution capture
    mgr.stop()


def test_mjpeg_stream_parts_and_end_when_capture_stops(monkeypatch):
    from app.capture.source import capture_manager
    from app.routers.capture import mjpeg_frames

    monkeypatch.setattr(CaptureManager, "_open", staticmethod(lambda source: _MovingFakeCap()))
    capture_manager.start("uvc:0")
    parts = list(mjpeg_frames(max_frames=2, fps=1000))
    assert len(parts) == 2
    assert all(p.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n") and b"\xff\xd8" in p for p in parts)
    capture_manager.stop()
    assert list(mjpeg_frames(fps=1000)) == []  # stopped: the stream ends instead of hanging


def test_preview_endpoint(env, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.capture.source import capture_manager
    from app.main import app

    monkeypatch.setattr(CaptureManager, "_open", staticmethod(lambda source: _MovingFakeCap()))
    # TestClient waits for the whole body, so let the "camera" drop after 3 frames to end the stream.
    real_preview, calls = capture_manager.preview_jpeg, []

    def three_frames():
        calls.append(1)
        if len(calls) > 3:
            raise RuntimeError("source dropped")
        return real_preview()

    monkeypatch.setattr(capture_manager, "preview_jpeg", three_frames)
    with TestClient(app) as client:
        assert client.get("/capture/preview").status_code == 409  # not started
        client.post("/capture/start", json={"source": "uvc:0"})
        r = client.get("/capture/preview")
        assert r.status_code == 200
        assert r.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
        assert r.content.count(b"--frame\r\nContent-Type: image/jpeg") == 3
    capture_manager.stop()
