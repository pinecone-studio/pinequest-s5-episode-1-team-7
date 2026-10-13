import time
from typing import Iterator, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from .. import ingest, pipeline
from ..capture.source import capture_manager
from ..schemas import CaptureStartIn, IngestOut, SnapshotIn
from ..states import SlideState

router = APIRouter(prefix="/capture", tags=["capture"])

PREVIEW_FPS = 8
_BOUNDARY = "frame"


@router.get("/status")
def status():
    return capture_manager.status


@router.post("/start")
def start(body: CaptureStartIn):
    try:
        capture_manager.start(body.source)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except ConnectionError as exc:
        raise HTTPException(502, str(exc))
    return capture_manager.status


@router.post("/stop")
def stop():
    capture_manager.stop()
    return capture_manager.status


def mjpeg_frames(max_frames: Optional[int] = None, fps: float = PREVIEW_FPS) -> Iterator[bytes]:
    """multipart/x-mixed-replace parts with preview JPEGs; ends when the capture stops or drops."""
    sent = 0
    while max_frames is None or sent < max_frames:
        try:
            jpeg = capture_manager.preview_jpeg()
        except RuntimeError:
            return
        yield (
            f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode()
            + jpeg
            + b"\r\n"
        )
        sent += 1
        time.sleep(1 / fps)


@router.get("/preview")
def preview():
    """Live MJPEG preview of the active source, so the technician can frame and focus before a
    snapshot (TDD 2.1). Works as a plain <img src>. Display only: snapshots stay full resolution."""
    if not capture_manager.status["active"]:
        raise HTTPException(409, "capture is not started")
    return StreamingResponse(
        mjpeg_frames(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/snapshot", response_model=IngestOut, status_code=202)
def snapshot(body: SnapshotIn, background: BackgroundTasks):
    """Grab the current frame from the phone and push it through the normal ingest pipeline."""
    try:
        frame = capture_manager.snapshot_jpeg()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    try:
        slide_id = ingest.ingest_bytes(frame, body.patient_id, body.indication)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    background.add_task(pipeline.process_slide, slide_id)
    return IngestOut(id=slide_id, state=SlideState.NEW.value)
