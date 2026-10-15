"""Drop blank microscope background before inference (TDD 5.2, 3.1 step 3, 8.1).

Tissue is found by its H&E colour, not by how saturated it is. Haematoxylin (purple)
and eosin (pink) both absorb green, so in tissue green is below both red and blue.
Glass, fat and gaps are white, and a phone's colour cast tints them yellow, green or
blue, never with green lowest. So the "magenta" signal min(R, B) - G separates pale
tissue from tinted background, where saturation could not: on phones, tinted glass is
as saturated as pale eosin, and saturation thresholds marked yellow lumen as tissue
while dropping pale tissue (checked on PLISM's phone vs scanner photos of the same
fields; see engine/README.md, "Tissue mask").
  - Cast correction: if the brightest pixels (the background, or the palest tissue)
    have green above red or blue, the photo has a green / yellow cast, and that amount
    is added back, scaled by each pixel's brightness. It is never subtracted, so an
    all-pink photo with no background is not erased.
  - The signal is smoothed over 5x5 pixels, so sensor and JPEG noise on white is not
    tissue, and Otsu picks the threshold per image, clamped to MAGENTA_THRESHOLD_RANGE.
  - Very dark pixels (eyepiece vignette) are excluded.
Re-check the thresholds once we have real smartphone captures.
"""
from dataclasses import replace

import cv2
import numpy as np

from .tiling import Tiles

MAGENTA_THRESHOLD_RANGE = (4, 10)  # clamp for the Otsu threshold on min(R, B) - G, 0-255 scale; a higher
# cap follows strongly stained areas up and drops pale tissue again, lower risks pinkish casts
MIN_VALUE = 30                     # ignore near-black pixels (eyepiece vignette)
MIN_TISSUE_FRACTION = 0.5          # keep patches that are at least half tissue
BRIGHT_PERCENTILE = 95             # pixels used to estimate the photo's colour cast
SMOOTHING = 5                      # box filter size for the magenta signal, pixels


def _colour_cast(image: np.ndarray) -> tuple:
    """(cast, reference brightness) from the brightest pixels of a small copy of the image.

    cast < 0 means green is above red or blue there: a green / yellow cast.
    """
    scale = min(1.0, 512 / max(image.shape[:2]))  # statistics only; full resolution is slow
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    r, g, b = (small[..., i].astype(np.int16) for i in range(3))
    raw, value = np.minimum(r, b) - g, small.max(axis=2)
    valid = value >= MIN_VALUE
    if valid.sum() < 100:
        return 0.0, 1.0
    bright = valid & (value >= np.percentile(value[valid], BRIGHT_PERCENTILE))
    return float(np.median(raw[bright])), max(float(np.median(value[bright])), 1.0)


def magenta(image: np.ndarray) -> np.ndarray:
    """min(R, B) - G per pixel, cast-corrected and smoothed; float32 (H, W)."""
    r, g, b = cv2.split(image)
    raw = cv2.subtract(cv2.min(r, b), g, dtype=cv2.CV_32F)
    cast, reference = _colour_cast(image)
    if cast < 0:  # green / yellow cast: add it back, in proportion to brightness
        value = cv2.max(cv2.max(r, g), b)
        raw = cv2.scaleAdd(value.astype(np.float32), -cast / reference, raw)
    return cv2.blur(raw, (SMOOTHING, SMOOTHING))


def tissue_mask(image: np.ndarray) -> np.ndarray:
    """Return an (H, W) bool mask that is True where the RGB image shows tissue."""
    signal = magenta(image)
    as_uint8 = np.clip(signal, 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(as_uint8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = np.clip(otsu, *MAGENTA_THRESHOLD_RANGE)
    return (signal > threshold) & (cv2.max(cv2.max(image[..., 0], image[..., 1]), image[..., 2]) >= MIN_VALUE)


def tissue_fraction(mask: np.ndarray, tiles: Tiles) -> np.ndarray:
    """Fraction of tissue pixels in each tile, in the same order as tiles.patches.

    Padded edge areas count as background.
    """
    rows, cols = tiles.grid_shape
    size = tiles.patch_size
    height, width = mask.shape
    padded = np.pad(mask, ((0, rows * size - height), (0, cols * size - width)))
    per_tile = padded.reshape(rows, size, cols, size).mean(axis=(1, 3))
    return per_tile[tiles.coords[:, 0], tiles.coords[:, 1]]


def filter_tissue_patches(
    tiles: Tiles, image: np.ndarray, min_fraction: float = MIN_TISSUE_FRACTION, mask: np.ndarray = None
) -> Tiles:
    """Keep only the tiles whose tissue fraction is at least min_fraction.

    mask: the image's tissue_mask, if the caller already has it.
    """
    if mask is None:
        mask = tissue_mask(image)
    keep = tissue_fraction(mask, tiles) >= min_fraction
    return replace(tiles, patches=tiles.patches[keep], coords=tiles.coords[keep])


def equalize_lighting(image: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Even out uneven microscope lighting with CLAHE on the lightness channel (TDD 8.1)."""
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    lab[..., 0] = clahe.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
