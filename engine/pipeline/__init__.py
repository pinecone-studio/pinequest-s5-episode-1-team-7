"""Image pre-processing, inference, scoring and heatmap pipeline for the AI engine.

The backend calls `analyze_slide` (entry point `engine.pipeline:analyze_slide`); see the
contract in backend/app/engine_adapter.py and docs/PLAN.md.
"""
import os
import tempfile
import time

from .heatmap import render_heatmap, save_heatmap
from .inference import get_classifier
from .masking import filter_tissue_patches
from .tiling import load_image, tile_image


def analyze_slide(image_path: str) -> dict:
    """Score one slide image and write its heatmap PNG to a temp file (the backend moves it).

    risk_flag is left out, so the backend derives it from its thresholds. Raises
    FileNotFoundError if the AI model is missing (see pipeline/inference.py).
    """
    start = time.perf_counter()

    image = load_image(image_path)
    tiles = filter_tissue_patches(tile_image(image), image)

    probs = get_classifier().predict(tiles.patches)
    # TODO(step 6): replace with the slide-level aggregation formula.
    score = float(probs.max()) if len(probs) else 0.0

    fd, heatmap_path = tempfile.mkstemp(prefix="heatmap-", suffix=".png")
    os.close(fd)
    save_heatmap(render_heatmap(tiles, probs), heatmap_path)

    return {
        "score": score,
        "heatmap_path": heatmap_path,
        "num_patches": len(tiles.patches),
        "inference_ms": (time.perf_counter() - start) * 1000.0,
    }
