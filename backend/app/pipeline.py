"""Background processing of one slide: NEW -> ... -> QUEUED (TDD 3.1)."""
import logging
import shutil
import threading
from pathlib import Path
from typing import Optional

from . import config, db, queue
from .engine_adapter import AnalysisResult, call_engine, default_organ, get_model_info, load_engine
from .states import SlideState

log = logging.getLogger(__name__)

# Limits parallel inference so a low-spec clinic PC does not lag (TDD 8.1).
_inference_slots = threading.BoundedSemaphore(config.MAX_CONCURRENT_INFERENCE)


def _store_heatmap(slide_id: int, src: Optional[str]) -> Optional[str]:
    """Move the engine's heatmap PNG into managed storage as heatmaps/<id>.png."""
    if not src:
        return None
    src_path = Path(src)
    if not src_path.is_file():
        raise FileNotFoundError(f"engine reported a heatmap that does not exist: {src}")
    config.HEATMAPS_DIR.mkdir(parents=True, exist_ok=True)
    dst = config.HEATMAPS_DIR / f"{slide_id}.png"
    if src_path.resolve() != dst.resolve():
        shutil.move(str(src_path), str(dst))
    return str(dst)


def _mark_failed(slide_id: int, exc: Exception) -> None:
    msg = f"{type(exc).__name__}: {exc}"[:500]
    try:
        with db.session() as conn:
            queue.transition(conn, slide_id, SlideState.FAILED, note=msg, error=msg)
    except Exception:  # e.g. slide already left the pipeline; never raise from a background task
        log.exception("could not mark slide %s as failed", slide_id)


def process_slide(slide_id: int) -> None:
    try:
        with db.session() as conn:
            queue.transition(conn, slide_id, SlideState.IMAGE_PROCESSING)
            row = queue.get_slide(conn, slide_id)
            image_path, um_per_px = row["image_path"], row["um_per_px"]
            organ = row["organ"] or default_organ()  # slides from before organs existed
        with db.session() as conn:
            queue.transition(conn, slide_id, SlideState.AI_RUNNING)
        with _inference_slots:
            raw = call_engine(load_engine(), image_path, um_per_px, organ)
        result = AnalysisResult.from_dict(raw)
        heatmap = _store_heatmap(slide_id, result.heatmap_path)
        info = get_model_info(organ)
        if info and isinstance(info.get("file"), dict):
            model_name = info["file"].get("name") or "engine"
            model_sha256 = info["file"].get("sha256")
        else:  # stub scorer or an engine predating model_info(): label honestly
            model_name, model_sha256 = "stub", None
        with db.session() as conn:
            queue.set_score(conn, slide_id, result.score, result.risk_flag, heatmap,
                            result.num_patches, result.inference_ms, result.scale_warning,
                            model_name, model_sha256)
    except Exception as exc:
        log.exception("slide %s failed", slide_id)
        _mark_failed(slide_id, exc)
