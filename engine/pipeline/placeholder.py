"""PLACEHOLDER patch scorer, used until the real model exists (steps 3-5).

This is NOT a model and says nothing about malignancy. It scores patches by how strongly
stained they are, only so the end-to-end flow (backend queue, heatmap, UI) can be tested.
"""
import cv2
import numpy as np


def placeholder_patch_scores(patches: np.ndarray) -> np.ndarray:
    """Return one value in [0, 1] per patch: mean HSV saturation, scaled."""
    if len(patches) == 0:
        return np.zeros(0, dtype=np.float32)
    flat = patches.reshape(-1, patches.shape[2], 3)  # stack patches vertically for one cvtColor
    saturation = cv2.cvtColor(flat, cv2.COLOR_RGB2HSV)[..., 1].reshape(len(patches), -1)
    return np.clip(saturation.mean(axis=1) / 255.0 * 1.5, 0.0, 1.0).astype(np.float32)
