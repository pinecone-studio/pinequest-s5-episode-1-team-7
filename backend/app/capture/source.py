"""Smartphone -> PC transport (TDD 2.1).

Source strings:
  "uvc:0"                       USB webcam emulation (phone as a UVC camera, device index 0)
  "rtsp://192.168.0.5:8554/x"   local Wi-Fi RTSP stream  (http:// / https:// MJPEG streams also work)
"""
import threading
from typing import Optional

import cv2


class CaptureManager:
    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._source: Optional[str] = None
        self._lock = threading.Lock()

    @staticmethod
    def _validate(source: str) -> None:
        """Reject malformed source strings without touching any hardware."""
        if source.startswith("uvc:"):
            try:
                int(source[4:] or 0)
            except ValueError:
                raise ValueError("uvc source must look like 'uvc:0'")
        elif source.startswith(("rtsp://", "http://", "https://")):
            return
        else:
            raise ValueError("source must be 'uvc:<index>' or an rtsp:// / http:// URL")

    @staticmethod
    def _open(source: str) -> cv2.VideoCapture:
        if source.startswith("uvc:"):
            try:
                index = int(source[4:] or 0)
            except ValueError:
                raise ValueError("uvc source must look like 'uvc:0'")
            cap = cv2.VideoCapture(index)
        elif source.startswith(("rtsp://", "http://", "https://")):
            cap = cv2.VideoCapture(source)
        else:
            raise ValueError("source must be 'uvc:<index>' or an rtsp:// / http:// URL")
        if not cap.isOpened():
            cap.release()
            raise ConnectionError(f"cannot open source {source}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)   # TDD 2.1: 1080p request
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        return cap

    def start(self, source: str) -> None:
        """Open a source (replacing any active one). ValueError: bad string, ConnectionError: unreachable."""
        self._validate(source)  # fail fast on malformed strings, before touching hardware
        new_cap = self._open(source)
        with self._lock:
            self._release()
            self._cap, self._source = new_cap, source

    def stop(self) -> None:
        with self._lock:
            self._release()

    def _release(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap, self._source = None, None

    @property
    def status(self) -> dict:
        return {"active": self._cap is not None, "source": self._source}

    def snapshot_jpeg(self) -> bytes:
        """Return the freshest frame as JPEG bytes. RuntimeError if not started or no frame."""
        with self._lock:
            if self._cap is None:
                raise RuntimeError("capture is not started")
            frame = None
            for _ in range(3):  # discard buffered frames so we get the most recent one
                ok, grabbed = self._cap.read()
                if ok and grabbed is not None:
                    frame = grabbed
            if frame is None:
                raise RuntimeError("failed to read a frame from the source")
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                raise RuntimeError("failed to encode the frame")
            return buf.tobytes()

    def preview_jpeg(self, max_side: int = 960, quality: int = 70) -> bytes:
        """A small JPEG of the current frame for the live preview (framing and focusing only; captures
        use snapshot_jpeg() at full resolution). RuntimeError if not started or no frame."""
        with self._lock:
            if self._cap is None:
                raise RuntimeError("capture is not started")
            self._cap.grab()  # skip one buffered frame, so the preview stays close to real time
            ok, frame = self._cap.read()
        if not ok or frame is None:
            raise RuntimeError("failed to read a frame from the source")
        height, width = frame.shape[:2]
        scale = max_side / max(height, width)
        if scale < 1:
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("failed to encode the frame")
        return buf.tobytes()


capture_manager = CaptureManager()
