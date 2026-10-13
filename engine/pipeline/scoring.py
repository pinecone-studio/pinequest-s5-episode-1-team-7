"""Slide-level triage score and Red / Yellow / Green flag (TDD 3.1 step 5, 6.1).

TDD formula, applied to patch log-odds (logit P) rather than probabilities:

    z = W_MAX * max(logit P) + (1 - W_MAX) * mean(top-K logit P)
    S_slide = sigmoid(z / TEMPERATURE)

The model is very confident, so in probability space slide scores pile up just below 1.0
(thresholds would sit at 0.99x and slides would tie). Log-odds keep them apart, and the
temperature spreads S over [0, 1] without changing the order. Averaging the top K patches
means one stray high patch (dust, a fold) can't flag a slide by itself.

W_MAX, TOP_K and the thresholds were chosen on slides simulated from PCam validation
patches (training/tune_scoring.py, results in training/results/slide_scoring.json):
red catches ~5% of normal slides, yellow-or-red ~25%. They belong to the model in
model/model_fp32.onnx (currently the Hibou-B-distilled student): re-run tune_scoring
whenever that file changes. They are a starting point for the team (PLAN step 6) and must
be re-tuned on real smartphone captures.
"""
import numpy as np

W_MAX = 0.0  # the search preferred the top-k mean alone; the max term stays available
TOP_K = 3
TEMPERATURE = 4.0
RED_THRESHOLD = 0.81
YELLOW_THRESHOLD = 0.70
_EPS = 1e-7  # keeps logit finite for probabilities of exactly 0 or 1


def logit(probs: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probs, dtype=np.float64), _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def slide_logit(probs: np.ndarray, w_max: float = W_MAX, top_k: int = TOP_K) -> float:
    """z: weighted max and top-k mean of the patch log-odds. Needs at least one patch."""
    top = np.sort(logit(probs))[::-1][:top_k]
    return float(w_max * top[0] + (1 - w_max) * top.mean())


def to_score(z) -> np.ndarray:
    """Map slide log-odds to S_slide in [0, 1]."""
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=np.float64) / TEMPERATURE))


def slide_score(probs: np.ndarray, w_max: float = W_MAX, top_k: int = TOP_K) -> float:
    """S_slide in [0, 1]; 0.0 when no tissue patches were found."""
    if len(probs) == 0:
        return 0.0
    return float(to_score(slide_logit(probs, w_max, top_k)))


def risk_flag(score: float, red: float = RED_THRESHOLD, yellow: float = YELLOW_THRESHOLD) -> str:
    if score >= red:
        return "red"
    if score >= yellow:
        return "yellow"
    return "green"
