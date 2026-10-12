from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from .. import db, pipeline, queue
from ..schemas import ActionIn, EventOut, SlideOut
from ..states import InvalidTransition, SlideState

router = APIRouter(tags=["slides"])


def _get_or_404(conn, slide_id: int):
    row = queue.get_slide(conn, slide_id)
    if row is None:
        raise HTTPException(404, "slide not found")
    return row


@router.get("/queue", response_model=list[SlideOut])
def get_queue(sort: str = Query("risk", pattern="^(risk|time)$")):
    """Priority worklist. Default: descending AI risk score (TDD 6.1)."""
    with db.session() as conn:
        return [SlideOut.from_row(r) for r in queue.list_queue(conn, sort)]


@router.get("/slides", response_model=list[SlideOut])
def list_slides(state: str | None = None):
    with db.session() as conn:
        return [SlideOut.from_row(r) for r in queue.list_all(conn, state)]


@router.get("/slides/{slide_id}", response_model=SlideOut)
def get_slide(slide_id: int):
    with db.session() as conn:
        return SlideOut.from_row(_get_or_404(conn, slide_id))


@router.get("/slides/{slide_id}/events", response_model=list[EventOut])
def get_events(slide_id: int):
    with db.session() as conn:
        _get_or_404(conn, slide_id)
        return [EventOut.from_row(e) for e in queue.list_events(conn, slide_id)]


@router.get("/slides/{slide_id}/image")
def get_image(slide_id: int):
    with db.session() as conn:
        path = _get_or_404(conn, slide_id)["image_path"]
    if not Path(path).is_file():
        raise HTTPException(404, "image file missing")
    return FileResponse(path)


@router.get("/slides/{slide_id}/heatmap")
def get_heatmap(slide_id: int):
    with db.session() as conn:
        path = _get_or_404(conn, slide_id)["heatmap_path"]
    if not path or not Path(path).is_file():
        raise HTTPException(404, "heatmap not ready")
    return FileResponse(path, media_type="image/png")


@router.post("/slides/{slide_id}/open", response_model=SlideOut)
def open_slide(slide_id: int):
    """Pathologist selects a slide: QUEUED -> UNDER_REVIEW."""
    with db.session() as conn:
        _get_or_404(conn, slide_id)
        try:
            queue.transition(conn, slide_id, SlideState.UNDER_REVIEW)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc))
        return SlideOut.from_row(queue.get_slide(conn, slide_id))


@router.post("/slides/{slide_id}/action", response_model=SlideOut)
def slide_action(slide_id: int, body: ActionIn):
    """confirm_malignancy / mark_benign / request_biopsy archive an UNDER_REVIEW slide;
    reassign_priority sets a manual priority (0-1) and returns it to the worklist."""
    with db.session() as conn:
        _get_or_404(conn, slide_id)
        try:
            queue.apply_action(conn, slide_id, body.action, body.priority)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return SlideOut.from_row(queue.get_slide(conn, slide_id))


@router.post("/slides/{slide_id}/retry", response_model=SlideOut, status_code=202)
def retry_slide(slide_id: int, background: BackgroundTasks):
    """Re-run the pipeline for a FAILED slide."""
    with db.session() as conn:
        _get_or_404(conn, slide_id)
        try:
            queue.transition(conn, slide_id, SlideState.NEW, note="retry", error=None)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc))
        out = SlideOut.from_row(queue.get_slide(conn, slide_id))
    background.add_task(pipeline.process_slide, slide_id)
    return out
