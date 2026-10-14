"""Shared ingestion used by POST /ingest (TDD 3.1 steps 1-2)."""
import os
import uuid
from typing import Optional

from . import anonymize, config, db, quality, queue, setups

ALLOWED_INDICATIONS = {"Routine", "Urgent"}


def ingest_bytes(data: bytes, patient_id: Optional[str], indication: str = "Routine",
                 setup_id: Optional[int] = None, objective: Optional[str] = None) -> int:
    """Validate, anonymize and store an image, then create the slide record (state NEW). Returns slide id.

    setup_id/objective (issue #35) resolve the photo's µm/px from a calibrated setup
    profile; it is stored on the slide and passed to the engine. An objective without
    a setup, an unknown setup or a bad objective all raise ValueError.

    Raises ValueError for bad input (empty / too large / not an image / bad indication
    / too blurry when TRIAGE_SHARPNESS > 0).
    """
    if indication not in ALLOWED_INDICATIONS:
        raise ValueError("indication must be 'Routine' or 'Urgent'")
    if not data:
        raise ValueError("empty file")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"file larger than {config.MAX_UPLOAD_MB} MB")
    if setup_id is None and objective is not None:
        raise ValueError("objective needs a setup_id (calibrate a setup first)")
    um_per_px: Optional[float] = None
    if setup_id is not None:
        with db.session() as conn:
            try:
                um_per_px = setups.um_per_px_for(conn, setup_id, objective)
            except KeyError:
                raise ValueError(f"unknown setup_id: {setup_id}")
    clean, ext = anonymize.strip_exif(data)
    quality.check_sharpness(clean, config.SHARPNESS_THRESHOLD, um_per_px)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.IMAGES_DIR / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(clean)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    try:
        with db.session() as conn:
            return queue.create_slide(conn, anonymize.hash_patient_id(patient_id), indication, str(path),
                                      setup_id, objective, um_per_px)
    except Exception:
        path.unlink(missing_ok=True)
        raise
