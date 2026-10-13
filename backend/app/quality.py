"""Capture-time image quality gate (TDD 8.1).

Out-of-focus / optically distorted photos cause false negatives and inaccurate
AI scoring, so blurry captures are rejected at ingestion (HTTP 422) instead of
wasting inference time and queue space.

Method: variance of the Laplacian on grayscale. In-focus textured images score
in the hundreds or thousands; heavily blurred ones score in the single digits
(solid-colour images score 0, which is why the gate is opt-in — see config).
"""
import cv2
import numpy as np


def sharpness_score(data: bytes) -> float:
    """Laplacian variance of `data` (any decodable image format).

    Raises ValueError if `data` cannot be decoded.
    """
    bgr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("not a valid image")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def check_sharpness(data: bytes, threshold: float) -> float:
    """Return the sharpness score, rejecting the image when it is blurry.

    A `threshold` <= 0 disables the gate (always passes). Otherwise images
    scoring below the threshold raise ValueError telling the technician to
    retake the capture in focus.
    """
    score = sharpness_score(data)
    if threshold > 0 and score < threshold:
        raise ValueError(
            f"image is too blurry (sharpness {score:.1f} < {threshold:g}); "
            "retake the capture in focus"
        )
    return score
