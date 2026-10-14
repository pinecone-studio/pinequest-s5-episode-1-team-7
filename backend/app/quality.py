"""Capture-time image quality gate (TDD 8.1).

Out-of-focus / optically distorted photos cause false negatives and inaccurate
AI scoring, so blurry captures are rejected at ingestion (HTTP 422) instead of
wasting inference time and queue space.

Method: variance of the Laplacian on grayscale, measured at a fixed working
size (larger images are downscaled first). Raw Laplacian variance grows with
resolution (measured ~4x per 2x edge on white noise), so without this a
threshold picked on small tiles would be meaningless on 12 MP phone photos.
After normalisation the same content scores within ~15% whether captured at
2048 or 4096 px on the long edge, and sharp/blurred separate by orders of
magnitude — but absolute scores still depend on magnification, staining and
tissue content:

| Images (issue #40) | Laplacian-variance sharpness |
|---|---|
| PLISM, sharp scanner tiles (all 7 scanners) | median 11–88 |
| PLISM, sharp smartphone tiles (all 6 phones) | median 17–90 |
| PCam test mosaics (inflated by tile edges) | 510–610 |
| Same mosaic, slightly / heavily blurred | 25 / 2.6 |

So there is no universal threshold: **calibrate per setup** (microscope +
phone + adapter + objective). Collect a few sharp captures and a few
deliberately defocused ones, then run (from `backend/`)::

    python -m app.quality sharp_dir/ blurry_dir/

which prints both distributions and suggests a `TRIAGE_SHARPNESS` value. The
gate stays off (`<= 0`) until a validated value is set — the desktop app
passes it once validated (issue #40), clinic IT can always override it.
Magnification itself is calibrated separately (issue #35).
"""
import argparse
import math
import statistics
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

# Longest edge, in pixels, that sharpness is measured at. Larger images are
# downscaled (INTER_AREA) before scoring; smaller ones are scored native
# (never upscaled, which would smooth them and fake a low score). Besides
# making one threshold work across capture resolutions, this keeps the check
# cheap on low-spec clinic PCs (a 12 MP photo scores as ~1 MP).
WORKING_EDGE = 1024


def _to_working_size(gray: np.ndarray) -> np.ndarray:
    edge = max(gray.shape[0], gray.shape[1])
    if edge <= WORKING_EDGE:
        return gray
    scale = WORKING_EDGE / edge
    return cv2.resize(
        gray,
        (round(gray.shape[1] * scale), round(gray.shape[0] * scale)),
        interpolation=cv2.INTER_AREA,
    )


def sharpness_score(data: bytes) -> float:
    """Laplacian variance of `data` (any decodable image format).

    Measured at `WORKING_EDGE`, so captures of the same content at different
    resolutions score nearly the same. Raises ValueError if undecodable.
    """
    bgr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("not a valid image")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(_to_working_size(gray), cv2.CV_64F).var())


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


def score_dir(path: Path) -> dict[str, float]:
    """Score every decodable image in `path` (non-recursive). Unreadable files
    are skipped with a warning on stderr. Raises FileNotFoundError for a
    missing directory."""
    if not path.is_dir():
        raise FileNotFoundError(f"not a directory: {path}")
    scores: dict[str, float] = {}
    for entry in sorted(path.iterdir()):
        if not entry.is_file():
            continue
        try:
            scores[entry.name] = sharpness_score(entry.read_bytes())
        except ValueError:
            print(f"warning: skipping undecodable file {entry}", file=sys.stderr)
    return scores


def suggest_threshold(sharp: Sequence[float], blurry: Sequence[float]) -> tuple[float, bool]:
    """Suggest a threshold separating `sharp` from `blurry` scores.

    Returns (threshold, separable). The suggestion is the geometric mean of
    the lowest sharp score and the highest blurry score; `separable` is False
    when the two sets overlap (lowest sharp <= highest blurry) or either set
    is empty. Raises ValueError when a set is empty.
    """
    if not sharp or not blurry:
        raise ValueError("need at least one sharp and one blurry score")
    lo_sharp, hi_blurry = min(sharp), max(blurry)
    return math.sqrt(lo_sharp * hi_blurry), lo_sharp > hi_blurry


def _summarise(name: str, scores: Sequence[float]) -> str:
    return (f"{name}: n={len(scores)} "
            f"min={min(scores):.1f} median={statistics.median(scores):.1f} max={max(scores):.1f}")


def main(argv: Sequence[str] | None = None) -> int:
    """Calibrate the blur gate: score two folders and suggest TRIAGE_SHARPNESS.

    Returns 0 when the sets separate cleanly, 1 when they overlap (pick a
    value by hand or take better calibration photos), 2 on usage errors.
    """
    parser = argparse.ArgumentParser(
        description="Suggest TRIAGE_SHARPNESS from sharp vs defocused calibration captures "
                    "(one setup + objective per run).")
    parser.add_argument("sharp_dir", type=Path, help="folder of sharp captures")
    parser.add_argument("blurry_dir", type=Path, help="folder of deliberately defocused captures")
    args = parser.parse_args(argv)

    try:
        sharp = score_dir(args.sharp_dir)
        blurry = score_dir(args.blurry_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not sharp or not blurry:
        print("error: need at least one scorable image in each folder", file=sys.stderr)
        return 2

    print(_summarise("sharp ", list(sharp.values())))
    print(_summarise("blurry", list(blurry.values())))
    threshold, separable = suggest_threshold(list(sharp.values()), list(blurry.values()))
    if separable:
        lo_sharp, hi_blurry = min(sharp.values()), max(blurry.values())
        print(f"suggested TRIAGE_SHARPNESS={threshold:.2f} "
              f"(lowest sharp {lo_sharp / threshold:.1f}x above, "
              f"highest blurry {threshold / hi_blurry:.1f}x below)")
        return 0
    print(f"warning: sets overlap — no clean threshold (geometric mean would be {threshold:.2f}); "
          f"retake calibration photos or pick a value by hand", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
