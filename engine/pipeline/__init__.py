"""Image pre-processing, inference, scoring and heatmap pipeline for the AI engine.

The backend calls `analyze_slide` (entry point `engine.pipeline:analyze_slide`); see the
contract in backend/app/engine_adapter.py and docs/PLAN.md.
"""
import os
import tempfile
import time
from typing import Optional

import cv2

from .heatmap import render_heatmap, save_heatmap
from .inference import get_classifier
from .masking import filter_tissue_patches, tissue_mask
from .scale import NO_CALIBRATION_WARNING, to_model_scale
from .scoring import risk_flag, slide_score
from .tiling import load_image, tile_image


def analyze_slide(image_path: str, um_per_px: Optional[float] = None) -> dict:
    """Score one slide image and write its heatmap PNG to a temp file (the backend moves it).

    um_per_px: the capture's calibrated µm per pixel (setup calibration and objective, issue
    #35). The photo is resized to the model's 0.42 µm/px before tiling; the heatmap stays the
    size of the original photo. None analyses the photo as-is and sets scale_warning.

    risk_flag comes from the engine's thresholds (pipeline/scoring.py), which are tuned to
    this model's scores, so the backend's own TRIAGE_RED / TRIAGE_YELLOW are not used. Raises
    FileNotFoundError if the AI model is missing (see pipeline/inference.py), and ValueError
    for an unreadable image or an implausible um_per_px (see pipeline/scale.py).
    """
    start = time.perf_counter()

    original = load_image(image_path)
    image = original if um_per_px is None else to_model_scale(original, um_per_px)
    tissue = tissue_mask(image)
    tiles = filter_tissue_patches(tile_image(image), image, mask=tissue)

    probs = get_classifier().predict(tiles.patches)
    score = slide_score(probs)

    layer = render_heatmap(tiles, probs, tissue)
    if layer.shape[:2] != original.shape[:2]:
        layer = cv2.resize(layer, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_LINEAR)
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
        "scale_warning": NO_CALIBRATION_WARNING if um_per_px is None else None,
    }
