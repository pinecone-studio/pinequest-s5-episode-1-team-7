"""Patch-probability heatmap layer for the viewer's overlay (TDD 2.3, 3.1 step 7, 6.2).

The layer is an RGBA PNG the size of the original image:
  - colour: patch P_malignant, interpolated between tile centres (green 0, yellow 0.5, red 1)
  - alpha: opaque only on tissue pixels of scored tiles, transparent elsewhere (the UI
    applies the opacity slider)
  - hotspots: tiles with P >= HOTSPOT_PROB (clipped to tissue, adjacent tiles merged) are
    outlined in a bright colour, so the pathologist's eye goes to them first (TDD 6.2
    "visual focus cues"). Outlines use whole tiles rather than the interpolated colours,
    which would shrink a single confident tile below the minimum size.
"""
import cv2
import numpy as np

from .tiling import Tiles

# Low -> moderate -> high probability, RGB.
GREEN = np.array([0, 200, 0], dtype=np.float32)
YELLOW = np.array([255, 210, 0], dtype=np.float32)
RED = np.array([230, 0, 0], dtype=np.float32)
HOTSPOT_COLOR = (0, 230, 255)   # bright cyan: stands out against green, yellow and red
HOTSPOT_PROB = 0.8              # outline regions the model is confident about
MIN_HOTSPOT_TILES = 0.25        # ignore hotspots smaller than a quarter of a tile


def probability_colors(probs: np.ndarray) -> np.ndarray:
    """Map probabilities in [0, 1] to RGB: green at 0, yellow at 0.5, red at 1."""
    p = np.clip(probs, 0.0, 1.0)[:, None]
    low = GREEN + (YELLOW - GREEN) * (p / 0.5)
    high = YELLOW + (RED - YELLOW) * ((p - 0.5) / 0.5)
    return np.where(p < 0.5, low, high).astype(np.uint8)


_LUT = probability_colors(np.linspace(0.0, 1.0, 256))  # uint8 colour per quantised probability


def _probability_map(tiles: Tiles, probs: np.ndarray) -> tuple:
    """(P per pixel, scored-tile mask), both (H, W). P is interpolated between the centres
    of scored tiles only, so unscored background tiles don't pull it towards 0."""
    rows, cols = tiles.grid_shape
    value = np.zeros((rows, cols), dtype=np.float32)
    weight = np.zeros((rows, cols), dtype=np.float32)
    value[tiles.coords[:, 0], tiles.coords[:, 1]] = probs
    weight[tiles.coords[:, 0], tiles.coords[:, 1]] = 1.0

    size = (cols * tiles.patch_size, rows * tiles.patch_size)
    num = cv2.resize(value * weight, size, interpolation=cv2.INTER_LINEAR)
    den = cv2.resize(weight, size, interpolation=cv2.INTER_LINEAR)
    nearest = cv2.resize(value, size, interpolation=cv2.INTER_NEAREST)
    p = np.where(den > 1e-6, num / np.maximum(den, 1e-6), nearest)
    scored = cv2.resize(weight, size, interpolation=cv2.INTER_NEAREST) > 0

    height, width = tiles.image_shape
    return p[:height, :width], scored[:height, :width]


def _outline_hotspots(layer: np.ndarray, tiles: Tiles, probs: np.ndarray, visible: np.ndarray) -> None:
    """Draw bright contours around confident tiles, in place."""
    rows, cols = tiles.grid_shape
    hot_tiles = np.zeros((rows, cols), dtype=np.uint8)
    confident = probs >= HOTSPOT_PROB
    hot_tiles[tiles.coords[confident, 0], tiles.coords[confident, 1]] = 1
    if not hot_tiles.any():
        return
    size = tiles.patch_size
    height, width = tiles.image_shape
    hot = cv2.resize(hot_tiles, (cols * size, rows * size), interpolation=cv2.INTER_NEAREST)[:height, :width]
    hot = (hot.astype(bool) & visible).astype(np.uint8)

    contours, _ = cv2.findContours(hot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = MIN_HOTSPOT_TILES * size ** 2
    contours = [c for c in contours if cv2.contourArea(c) >= min_area]
    thickness = max(2, min(layer.shape[:2]) // 300)
    cv2.drawContours(layer, contours, -1, (*HOTSPOT_COLOR, 255), thickness)


def render_heatmap(tiles: Tiles, probs: np.ndarray, tissue: np.ndarray = None) -> np.ndarray:
    """Build an RGBA layer the size of the original image.

    tissue: optional (H, W) bool tissue mask (masking.tissue_mask). With it, only tissue
    pixels are coloured; without it, whole scored tiles are.
    """
    height, width = tiles.image_shape
    layer = np.zeros((height, width, 4), dtype=np.uint8)
    if len(probs) == 0:
        return layer

    probs = np.asarray(probs, dtype=np.float32)
    p, scored = _probability_map(tiles, probs)
    visible = scored
    if tissue is not None:
        # Close small gaps (nuclei, lumen) so the overlay reads as regions, not speckle.
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        visible = scored & (cv2.morphologyEx(tissue.astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0)

    layer[..., :3] = _LUT[np.round(np.clip(p, 0.0, 1.0) * 255).astype(np.uint8)]
    layer[..., 3] = visible * np.uint8(255)
    _outline_hotspots(layer, tiles, probs, visible)
    return layer


def save_heatmap(layer: np.ndarray, path: str) -> None:
    """Write an RGBA layer as a PNG."""
    if not cv2.imwrite(str(path), cv2.cvtColor(layer, cv2.COLOR_RGBA2BGRA)):
        raise OSError(f"could not write heatmap: {path}")
