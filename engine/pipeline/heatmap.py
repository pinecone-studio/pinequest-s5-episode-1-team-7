"""Patch-probability heatmap layer for the viewer's overlay (TDD 2.3, 3.1 step 7)."""
import cv2
import numpy as np

from .tiling import Tiles

# Low -> moderate -> high probability, RGB.
GREEN = np.array([0, 200, 0], dtype=np.float32)
YELLOW = np.array([255, 210, 0], dtype=np.float32)
RED = np.array([230, 0, 0], dtype=np.float32)


def probability_colors(probs: np.ndarray) -> np.ndarray:
    """Map probabilities in [0, 1] to RGB: green at 0, yellow at 0.5, red at 1."""
    p = np.clip(probs, 0.0, 1.0)[:, None]
    low = GREEN + (YELLOW - GREEN) * (p / 0.5)
    high = YELLOW + (RED - YELLOW) * ((p - 0.5) / 0.5)
    return np.where(p < 0.5, low, high).astype(np.uint8)


def render_heatmap(tiles: Tiles, probs: np.ndarray) -> np.ndarray:
    """Build an RGBA layer the size of the original image.

    Each scored tile is filled with its probability colour and is fully opaque; tiles that
    were not scored (background) are transparent. The UI applies the opacity slider.
    """
    rows, cols = tiles.grid_shape
    grid = np.zeros((rows, cols, 4), dtype=np.uint8)
    if len(probs):
        grid[tiles.coords[:, 0], tiles.coords[:, 1], :3] = probability_colors(np.asarray(probs))
        grid[tiles.coords[:, 0], tiles.coords[:, 1], 3] = 255

    size = tiles.patch_size
    layer = cv2.resize(grid, (cols * size, rows * size), interpolation=cv2.INTER_NEAREST)
    height, width = tiles.image_shape
    return layer[:height, :width]


def save_heatmap(layer: np.ndarray, path: str) -> None:
    """Write an RGBA layer as a PNG."""
    if not cv2.imwrite(str(path), cv2.cvtColor(layer, cv2.COLOR_RGBA2BGRA)):
        raise OSError(f"could not write heatmap: {path}")
