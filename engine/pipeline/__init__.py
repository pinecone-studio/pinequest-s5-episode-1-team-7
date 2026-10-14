"""Image pre-processing, inference, scoring and heatmap pipeline for the AI engine.

The backend calls `analyze_slide` (entry point `engine.pipeline:analyze_slide`); see the
contract in backend/app/engine_adapter.py and docs/PLAN.md.
"""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .heatmap import render_heatmap, save_heatmap
from .inference import get_classifier, model_path
from .masking import filter_tissue_patches, tissue_mask
from .scale import MODEL_UM_PER_PX, NO_SCALE_INFO, to_model_scale  # noqa: F401 (re-exported)
from .scoring import risk_flag, slide_score
from .tiling import load_image, tile_image


def analyze_slide(image_path: str, um_per_px: Optional[float] = None) -> dict:
    """Score one slide image and write its heatmap PNG to a temp file (the backend moves it).

    um_per_px: the capture's calibrated µm per pixel (the backend's setup profile and
    objective, issue #35). The photo is resized to the model's 0.42 µm/px before tiling; the
    heatmap stays the size of the original photo. None analyses the photo as-is and reports
    scale_warning=NO_SCALE_INFO.

    risk_flag comes from the engine's thresholds (pipeline/scoring.py), which are tuned to
    this model's scores, so the backend's own TRIAGE_RED / TRIAGE_YELLOW are not used. Raises
    FileNotFoundError if the AI model is missing (see pipeline/inference.py), and ValueError
    for an unreadable image or an implausible um_per_px (see pipeline/scale.py).
    """
    start = time.perf_counter()

    original = load_image(image_path)
    if um_per_px is None:
        image, scale_warning = original, NO_SCALE_INFO
    else:
        image, um_per_px, scale_warning = to_model_scale(original, um_per_px), float(um_per_px), None
    tissue = tissue_mask(image)
    tiles = filter_tissue_patches(tile_image(image), image, mask=tissue)

    probs = get_classifier().predict(tiles.patches)
    score = slide_score(probs)

    layer = render_heatmap(tiles, probs, tissue)
    if layer.shape[:2] != original.shape[:2]:
        # Back to the original photo size: linear for colour, nearest for alpha so tissue
        # transparency is not smeared across edges.
        size = (original.shape[1], original.shape[0])
        rgb = cv2.resize(layer[..., :3], size, interpolation=cv2.INTER_LINEAR)
        alpha = cv2.resize(layer[..., 3], size, interpolation=cv2.INTER_NEAREST)
        layer = np.dstack([rgb, alpha])
    fd, heatmap_path = tempfile.mkstemp(prefix="heatmap-", suffix=".png")
    os.close(fd)
    save_heatmap(layer, heatmap_path)

    return {
        "score": score,
        "risk_flag": risk_flag(score),
        "heatmap_path": heatmap_path,
        "num_patches": len(tiles.patches),
        "inference_ms": (time.perf_counter() - start) * 1000.0,
        "um_per_px_used": um_per_px,
        "scale_warning": scale_warning,
    }


def model_info() -> dict:
    """The committed model card plus the live model file and provider (About the AI).

    Never raises: a missing card, model file, or inference session is reported
    in the result instead (the backend's GET /model and the desktop About page
    must work even when the engine is broken).
    """
    try:
        card = json.loads((Path(__file__).resolve().parents[1] / "model" / "model_card.json").read_text())
    except (OSError, ValueError):
        card = None
    path = None
    try:
        path = model_path()
    except Exception:
        path = None
    exists = bool(path is not None and path.is_file())
    sha256 = None
    if exists:
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    digest.update(chunk)
            sha256 = digest.hexdigest()
        except OSError:
            sha256 = None
    provider = None
    try:
        provider = get_classifier().provider
    except Exception:
        provider = None
    expected = card["file"]["sha256"] if isinstance(card, dict) else None
    return {
        "card": card,
        "file": {
            "path": str(path) if path is not None else None,
            "name": path.name if path is not None else None,
            "exists": exists,
            "sha256": sha256,
            "matches_card": bool(sha256) and sha256 == expected,
        },
        "provider": provider,
    }
