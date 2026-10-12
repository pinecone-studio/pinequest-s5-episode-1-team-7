"""Shared ingestion used by POST /ingest and the capture snapshot (TDD 3.1 steps 1-2)."""
import uuid
from typing import Optional

from . import anonymize, config, db, queue

ALLOWED_INDICATIONS = {"Routine", "Urgent"}


def ingest_bytes(data: bytes, patient_id: Optional[str], indication: str = "Routine") -> int:
    """Validate, anonymize and store an image, then create the slide record (state NEW). Returns slide id.

    Raises ValueError for bad input (empty / too large / not an image / bad indication).
    """
    if indication not in ALLOWED_INDICATIONS:
        raise ValueError("indication must be 'Routine' or 'Urgent'")
    if not data:
        raise ValueError("empty file")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"file larger than {config.MAX_UPLOAD_MB} MB")
    clean, ext = anonymize.strip_exif(data)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.IMAGES_DIR / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(clean)
    try:
        with db.session() as conn:
            return queue.create_slide(conn, anonymize.hash_patient_id(patient_id), indication, str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise
