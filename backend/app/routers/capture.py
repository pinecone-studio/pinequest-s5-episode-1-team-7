from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import ingest, pipeline
from ..capture.source import capture_manager
from ..schemas import CaptureStartIn, IngestOut, SnapshotIn
from ..states import SlideState

router = APIRouter(prefix="/capture", tags=["capture"])


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
