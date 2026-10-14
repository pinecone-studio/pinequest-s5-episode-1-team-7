"""Resize captures to the model's training magnification (issue #35, docs/PLAN.md).

The model only works at about 0.42 µm per pixel (PCam's ~0.97 µm/px patches enlarged from
96 to 224 px), and it cannot tell magnification from the photo. The caller passes the
setup's calibrated µm/px (stage micrometer + objective); the photo is resized by
um_per_px / MODEL_UM_PER_PX before tiling.
"""
import math

import cv2
import numpy as np

MODEL_UM_PER_PX = 0.42
# Plausible µm/px for a phone on a microscope (≈ 100× oil to 4× objective). Values outside
# this range are almost certainly a calibration or objective mistake; above the upper bound
# the image would also be enlarged more than ~5×, which invents detail and uses a lot of RAM.
UM_PER_PX_RANGE = (0.05, 2.0)
NO_CALIBRATION_WARNING = (
    "No magnification calibration: the photo was analysed at its original size. "
    "Scores are unreliable unless it is already at ~0.42 µm/px; calibrate the setup "
    "and choose the objective."
)


def rescale_factor(um_per_px: float) -> float:
    """How much to resize a photo taken at um_per_px to reach the model's scale."""
    low, high = UM_PER_PX_RANGE
    try:
        value = float(um_per_px)
    except (TypeError, ValueError):
        value = math.nan
    if isinstance(um_per_px, bool) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"um_per_px must be between {low} and {high} µm/px, got {um_per_px!r}")
    return value / MODEL_UM_PER_PX


def to_model_scale(image: np.ndarray, um_per_px: float) -> np.ndarray:
    """Resize an RGB image taken at um_per_px to MODEL_UM_PER_PX."""
    factor = rescale_factor(um_per_px)
    height, width = image.shape[:2]
    size = (max(1, round(width * factor)), max(1, round(height * factor)))
    if size == (width, height):
        return image
    interpolation = cv2.INTER_AREA if factor < 1 else cv2.INTER_LINEAR
    return cv2.resize(image, size, interpolation=interpolation)
