"""Split a high-resolution tissue image into uniform patches (TDD 3.1 step 3)."""
from dataclasses import dataclass

import cv2
import numpy as np

PATCH_SIZE = 224
# Brightfield microscope background is white, so padding with white keeps partial edge
# tiles and lets background masking (step 2) treat the padded area as empty.
PAD_VALUE = 255


@dataclass
class Tiles:
    patches: np.ndarray      # (N, patch_size, patch_size, 3) uint8, RGB
    coords: np.ndarray       # (N, 2) int, (row, col) grid position of each patch
    grid_shape: tuple        # (rows, cols) of the full grid
    image_shape: tuple       # (height, width) of the original, unpadded image
    patch_size: int


def load_image(path: str) -> np.ndarray:
    """Read an image file as an RGB uint8 array. Raises ValueError if it cannot be decoded."""
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"cannot decode image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def tile_image(image: np.ndarray, patch_size: int = PATCH_SIZE) -> Tiles:
    """Cut an RGB image into non-overlapping patch_size x patch_size tiles, row-major.

    Edges that do not fill a whole tile are padded with white rather than dropped, so
    tissue at the image border is still analysed.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"expected an RGB image of shape (H, W, 3), got {image.shape}")
    if patch_size <= 0:
        raise ValueError(f"patch_size must be positive, got {patch_size}")

    height, width = image.shape[:2]
    rows = -(-height // patch_size)  # ceil division
    cols = -(-width // patch_size)

    padded = np.pad(
        image,
        ((0, rows * patch_size - height), (0, cols * patch_size - width), (0, 0)),
        constant_values=PAD_VALUE,
    )
    # (rows, ps, cols, ps, 3) -> (rows, cols, ps, ps, 3) -> (N, ps, ps, 3)
    patches = (
        padded.reshape(rows, patch_size, cols, patch_size, 3)
        .swapaxes(1, 2)
        .reshape(-1, patch_size, patch_size, 3)
    )
    coords = np.stack(np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij"), axis=-1).reshape(-1, 2)

    return Tiles(
        patches=np.ascontiguousarray(patches),
        coords=coords,
        grid_shape=(rows, cols),
        image_shape=(height, width),
        patch_size=patch_size,
    )
