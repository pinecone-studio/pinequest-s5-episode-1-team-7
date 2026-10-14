"""Image pre-processing, inference, scoring and heatmap pipeline for the AI engine.

The backend calls `analyze_slide` (entry point `engine.pipeline:analyze_slide`); see the
contract in backend/app/engine_adapter.py and docs/PLAN.md.
"""
import math
import os
import tempfile
import time

import cv2
import numpy as np

from .heatmap import render_heatmap, save_heatmap
from .inference import get_classifier
from .masking import filter_tissue_patches, tissue_mask
from .scoring import risk_flag, slide_score
from .tiling import load_image, tile_image

# Training scale of the patch classifier (issue #35): PCam patches are ~0.97 µm/px
# at 96 px and the model sees them upsampled to 224 px, i.e. about 0.42 µm/px.
MODEL_UM_PER_PX = 0.42

# scale_warning value when the caller did not say what magnification the photo is at.
NO_SCALE_INFO = "no_scale_info"


def _rescale_to_model(image: np.ndarray, um_per_px: float) -> np.ndarray:
    """Resize `image` so one pixel is MODEL_UM_PER_PX wide (same pattern as
    training/plism_eval.py). Raises ValueError for non-positive values."""
    try:
        um = float(um_per_px)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"um_per_px must be a number, got {um_per_px!r}") from exc
    if not math.isfinite(um) or um <= 0:
        raise ValueError(f"um_per_px must be positive, got {um_per_px!r}")
    scale = um / MODEL_UM_PER_PX
    if scale == 1.0:
        return image
    return cv2.resize(image, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)


def analyze_slide(image_path: str, um_per_px: float | None = None) -> dict:
    """Score one slide image and write its heatmap PNG to a temp file (the backend moves it).

    um_per_px: microns per pixel of this photo (from the backend's calibrated setup
    profile, issue #35). The photo is resized to MODEL_UM_PER_PX before tiling so the
    model always sees its training magnification. None keeps the old behaviour (no
    resize) and reports scale_warning=NO_SCALE_INFO instead.

    The heatmap is always the size of the original photo. risk_flag comes from the
    engine's thresholds (pipeline/scoring.py), which are tuned to this model's scores,
    so the backend's own TRIAGE_RED / TRIAGE_YELLOW are not used. Raises
    FileNotFoundError if the AI model is missing (see pipeline/inference.py).
    """
    start = time.perf_counter()

    image = load_image(image_path)
    orig_shape = image.shape[:2]  # (H, W): the heatmap stays this size
    if um_per_px is None:
        scale_warning: str | None = NO_SCALE_INFO
    else:
        image = _rescale_to_model(image, um_per_px)
        um_per_px = float(um_per_px)
        scale_warning = None
    tissue = tissue_mask(image)
    tiles = filter_tissue_patches(tile_image(image), image, mask=tissue)

    probs = get_classifier().predict(tiles.patches)
    score = slide_score(probs)

    layer = render_heatmap(tiles, probs, tissue)
    if layer.shape[:2] != orig_shape:
        # Back to the original photo size: linear for colour, nearest for alpha
        # so tissue transparency is not smeared across edges.
        h0, w0 = orig_shape
        rgb = cv2.resize(layer[..., :3], (w0, h0), interpolation=cv2.INTER_LINEAR)
        alpha = cv2.resize(layer[..., 3], (w0, h0), interpolation=cv2.INTER_NEAREST)
        layer = np.dstack([rgb, alpha]).astype(np.uint8)
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
