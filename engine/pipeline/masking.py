"""Drop blank microscope background before inference (TDD 5.2, 3.1 step 3, 8.1).

Stained tissue is coloured, while background is white or grey (and the eyepiece
vignette is black), so tissue is detected on the HSV saturation channel:
  - Otsu picks the saturation threshold for each image, clamped to a sane range so a
    blank image does not get a noise-level threshold and an all-tissue image is not
    split in half.
  - Very dark pixels are excluded, since near-black noise can have high saturation.
Thresholds are first guesses; tune them once we have real smartphone captures.
"""
from dataclasses import replace

import cv2
import numpy as np

from .tiling import Tiles

SATURATION_THRESHOLD_RANGE = (20, 60)  # clamp for the Otsu threshold, 0-255 scale
MIN_VALUE = 30                         # ignore near-black pixels (eyepiece vignette)
MIN_TISSUE_FRACTION = 0.5              # keep patches that are at least half tissue


def tissue_mask(image: np.ndarray) -> np.ndarray:
    """Return an (H, W) bool mask that is True where the RGB image shows tissue."""
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    saturation, value = hsv[..., 1], hsv[..., 2]

    otsu, _ = cv2.threshold(saturation, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = np.clip(otsu, *SATURATION_THRESHOLD_RANGE)

    return (saturation > threshold) & (value >= MIN_VALUE)


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
