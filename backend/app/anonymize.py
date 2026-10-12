"""On-premise anonymization (TDD 7.1): salted patient-ID hash + EXIF/GPS stripping."""
import hashlib
import io
import os
import secrets
import uuid
from typing import Optional

import numpy as np
from PIL import Image, ImageOps

from . import config


def _salt() -> str:
    """TRIAGE_HASH_SALT if set, else a random salt generated once and kept in DATA_DIR/.salt."""
    if config.HASH_SALT:
        return config.HASH_SALT
    path = config.DATA_DIR / ".salt"
    if not path.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path.read_text().strip()


def hash_patient_id(patient_id: Optional[str]) -> str:
    """Stable salted hash, so the raw ID is never stored. No ID -> a random one-off ID."""
    pid = (patient_id or "").strip() or uuid.uuid4().hex
    return hashlib.sha256((_salt() + pid).encode()).hexdigest()[:16]


def strip_exif(data: bytes) -> tuple[bytes, str]:
    """Re-encode from pixel data only (drops EXIF/GPS/ICC/text chunks). Returns (bytes, extension).

    JPEG stays JPEG; everything else becomes lossless PNG. EXIF orientation is applied first.
    Raises ValueError if `data` is not a decodable image.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # unreadable, truncated, decompression bomb ...
        raise ValueError("not a valid image") from exc
    is_jpeg = (img.format or "").upper() == "JPEG"
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    clean = Image.fromarray(np.asarray(img))
    out = io.BytesIO()
    if is_jpeg:
        clean.save(out, format="JPEG", quality=95)
    else:
        clean.save(out, format="PNG")
    return out.getvalue(), ("jpg" if is_jpeg else "png")
