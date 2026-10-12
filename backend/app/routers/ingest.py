from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from .. import config, ingest, pipeline
from ..schemas import IngestOut
from ..states import SlideState

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestOut, status_code=202)
def ingest_image(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    indication: str = Form("Routine"),
):
    """Accept an image (multipart), anonymize + store it, and process it in the background."""
    # Sync endpoint -> FastAPI runs it in a worker thread, so PIL/SQLite never block the event loop.
    data = file.file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        slide_id = ingest.ingest_bytes(data, patient_id, indication)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    background.add_task(pipeline.process_slide, slide_id)
    return IngestOut(id=slide_id, state=SlideState.NEW.value)
