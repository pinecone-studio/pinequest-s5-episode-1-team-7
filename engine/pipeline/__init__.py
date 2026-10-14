"""Image pre-processing, inference, scoring and heatmap pipeline for the AI engine.

The backend calls `analyze_slide` (entry point `engine.pipeline:analyze_slide`); see the
contract in backend/app/engine_adapter.py and docs/PLAN.md.
"""
import hashlib
import json
import os
import tempfile
import time
from typing import Optional

import cv2
import numpy as np

from .heatmap import render_heatmap, save_heatmap
from .inference import get_classifier, model_path
from .masking import filter_tissue_patches, tissue_mask
from .organs import DEFAULT_ORGAN, available_organs, get_organ  # noqa: F401 (re-exported)
from .scale import MODEL_UM_PER_PX, NO_SCALE_INFO, to_model_scale  # noqa: F401 (re-exported)
from .scoring import risk_flag, slide_score
from .tiling import load_image, tile_image


def analyze_slide(image_path: str, um_per_px: Optional[float] = None, organ: Optional[str] = None) -> dict:
    """Score one slide image and write its heatmap PNG to a temp file (the backend moves it).

    um_per_px: the capture's calibrated µm per pixel (the backend's setup profile and
    objective, issue #35). The photo is resized to the organ model's training scale (0.42
    µm/px for lymph node) before tiling; the heatmap stays the size of the original photo.
    None analyses the photo as-is and reports scale_warning=NO_SCALE_INFO.

    organ: which organ's model scores the slide (issue #53, pipeline/organs.py); None means
    DEFAULT_ORGAN ("lymph_node"). There is no fallback to another organ's model.

    risk_flag comes from the organ model's thresholds, which are tuned to that model's
    scores, so the backend's own TRIAGE_RED / TRIAGE_YELLOW are not used. Raises
    FileNotFoundError if the organ's AI model is missing (see pipeline/inference.py), and
    ValueError for an unknown organ, an unreadable image or an implausible um_per_px (see
    pipeline/scale.py).
    """
    start = time.perf_counter()
    spec = get_organ(organ)

    original = load_image(image_path)
    if um_per_px is None:
        image, scale_warning = original, NO_SCALE_INFO
    else:
        image = to_model_scale(original, um_per_px, spec.um_per_px)
        um_per_px, scale_warning = float(um_per_px), None
    tissue = tissue_mask(image)
    tiles = filter_tissue_patches(tile_image(image), image, mask=tissue)

    probs = get_classifier(spec.organ).predict(tiles.patches)
    score = slide_score(probs, spec.w_max, spec.top_k)

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
        "risk_flag": risk_flag(score, spec.red, spec.yellow),
        "heatmap_path": heatmap_path,
        "num_patches": len(tiles.patches),
        "inference_ms": (time.perf_counter() - start) * 1000.0,
        "um_per_px_used": um_per_px,
        "scale_warning": scale_warning,
        "organ": spec.organ,
    }


def model_info(organ: Optional[str] = None) -> dict:
    """The organ model's committed card plus its live file and provider (About the AI).

    organ: as in analyze_slide (None = DEFAULT_ORGAN). Never raises: an unknown organ, a
    missing card, model file, or inference session is reported in the result instead (the
    backend's GET /model and the desktop About page must work even when the engine is broken).
    """
    try:
        spec = get_organ(organ)
    except ValueError:
        spec = None
    try:
        card = json.loads(spec.card_path.read_text())
    except (AttributeError, OSError, ValueError):
        card = None
    path = None
    try:
        path = model_path(organ)
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
        provider = get_classifier(organ).provider
    except Exception:
        provider = None
    card_file = card.get("file") if isinstance(card, dict) else None
    expected = card_file.get("sha256") if isinstance(card_file, dict) else None
    return {
        "organ": spec.organ if spec else organ,
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
