"""Choose the slide-score formula and risk-flag thresholds (step 6) on simulated slides.

There are no slide-level labels for smartphone captures yet, so slides are simulated from
real PCam patches scored by the exported model:
  - negative slide: n normal patches
  - positive slide: n patches of which a fraction f are tumour (f = 1% ... 50%)
with n drawn from 50-250 tissue patches (a 12 MP capture has ~200). Patches are sampled
independently, which ignores within-slide correlation (stain, focus), so treat the numbers
as a comparison between formulas rather than real-world accuracy.

The formula of pipeline/scoring.py, z = w_max * max(logit P) + (1 - w_max) * mean(top-k
logit P), is grid-searched on the validation split by mean slide AUC over all tumour
fractions. The flag thresholds are percentiles of the negative-slide scores S = to_score(z)
(red: RED_FALSE_ALARM of normal slides, yellow-or-red: YELLOW_FALSE_ALARM). Then everything
is reported once on the test split. Copy the chosen values into pipeline/scoring.py.

    python -m training.tune_scoring
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from pipeline.inference import DEFAULT_MODEL_PATH, PatchClassifier
from pipeline.scoring import logit, to_score
from training.pcam import DATA_DIR, PCamBatches

ENGINE_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = ENGINE_DIR / "data" / "cache"
RESULTS_PATH = ENGINE_DIR / "training" / "results" / "slide_scoring.json"

FRACTIONS = (0.01, 0.02, 0.05, 0.10, 0.25, 0.50)
W_MAX_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
TOP_K_GRID = (1, 2, 3, 5, 10, 20)
MAX_K = max(TOP_K_GRID)
RED_FALSE_ALARM = 0.05     # share of normal slides flagged red
YELLOW_FALSE_ALARM = 0.25  # share of normal slides flagged yellow or red


def patch_probs(model_path: Path, split: str, data_dir: Path) -> tuple:
    """(P_malignant, labels) for every patch of the split, cached per model file."""
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()[:12]
    cache = CACHE_DIR / f"pcam_{split}_probs_{digest}.npz"
    if cache.exists():
        data = np.load(cache)
        return data["probs"], data["labels"]
    dataset = PCamBatches.from_split(split, data_dir)
    classifier = PatchClassifier(model_path, batch_size=256)
    probs = []
    for start in range(0, len(dataset), 4096):
        images, _ = dataset[list(range(start, min(start + 4096, len(dataset))))]
        probs.append(classifier.predict(images.numpy()))
        print(f"\r  scoring {split}: {start + len(images)}/{len(dataset)}", end="", flush=True)
    print()
    probs, labels = np.concatenate(probs), dataset.labels.astype(np.int64)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(cache, probs=probs, labels=labels)
    return probs, labels


def simulate(logits, labels, fraction, n_slides, rng) -> np.ndarray:
    """(n_slides, MAX_K + 1): per slide [max, top-1 .. top-MAX_K means] of patch log-odds; fraction 0 = negative."""
    normal, tumour = logits[labels == 0], logits[labels == 1]
    rows = np.empty((n_slides, MAX_K + 1), dtype=np.float64)
    for i in range(n_slides):
        n = int(rng.integers(50, 251))
        m = max(1, round(fraction * n)) if fraction > 0 else 0
        slide = np.concatenate([rng.choice(tumour, m), rng.choice(normal, n - m)])
        top = -np.sort(-slide)[:MAX_K]
        rows[i, 0] = top[0]
        rows[i, 1:] = np.cumsum(top) / np.arange(1, MAX_K + 1)
    return rows


def scores(rows, w_max, k) -> np.ndarray:
    """S_slide for every simulated slide (same formula as pipeline.scoring.slide_score)."""
    return to_score(w_max * rows[:, 0] + (1 - w_max) * rows[:, k])


def slide_auc(neg, pos) -> float:
    return float(roc_auc_score(np.r_[np.zeros(len(neg)), np.ones(len(pos))], np.r_[neg, pos]))


def build_slides(probs, labels, n_slides, seed) -> dict:
    rng = np.random.default_rng(seed)
    logits = logit(probs)
    return {f: simulate(logits, labels, f, n_slides, rng) for f in (0.0, *FRACTIONS)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    p.add_argument("--slides", type=int, default=2000, help="simulated slides per tumour fraction")
    p.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = p.parse_args()

    valid = build_slides(*patch_probs(args.model, "valid", args.data_dir), args.slides, seed=0)
    test = build_slides(*patch_probs(args.model, "test", args.data_dir), args.slides, seed=1)

    grid = []
    for w_max in W_MAX_GRID:
        for k in TOP_K_GRID:
            neg = scores(valid[0.0], w_max, k)
            aucs = {f: slide_auc(neg, scores(valid[f], w_max, k)) for f in FRACTIONS}
            grid.append({"w_max": w_max, "top_k": k, "mean_auc": float(np.mean(list(aucs.values()))), "auc": aucs})
    best = max(grid, key=lambda g: g["mean_auc"])
    w_max, k = best["w_max"], best["top_k"]
    print(f"best on valid: w_max={w_max}, top_k={k}, mean AUC {best['mean_auc']:.4f}")
    for g in sorted(grid, key=lambda g: -g["mean_auc"])[:5]:
        print(f"  w_max={g['w_max']:.2f} k={g['top_k']:2d}  mean AUC {g['mean_auc']:.4f}")

    neg_valid = scores(valid[0.0], w_max, k)
    red = float(np.quantile(neg_valid, 1 - RED_FALSE_ALARM))
    yellow = float(np.quantile(neg_valid, 1 - YELLOW_FALSE_ALARM))
    print(f"thresholds: red >= {red:.3f}, yellow >= {yellow:.3f}")

    def report(slides):
        neg = scores(slides[0.0], w_max, k)
        out = {"normal_slides": {"red": float(np.mean(neg >= red)), "yellow_or_red": float(np.mean(neg >= yellow))}}
        for f in FRACTIONS:
            pos = scores(slides[f], w_max, k)
            out[f"tumour_{int(f * 100)}pct"] = {
                "auc": slide_auc(neg, pos), "red": float(np.mean(pos >= red)), "yellow_or_red": float(np.mean(pos >= yellow)),
            }
        return out

    baseline = {f"tumour_{int(f * 100)}pct": slide_auc(scores(test[0.0], 1.0, 1), scores(test[f], 1.0, 1)) for f in FRACTIONS}
    result = {
        "model": args.model.name,
        "chosen": {"w_max": w_max, "top_k": k, "red": round(red, 4), "yellow": round(yellow, 4)},
        "test": report(test),
        "test_auc_max_only": baseline,
        "valid_grid": grid,
        "setup": {"slides_per_fraction": args.slides, "patches_per_slide": "50-250", "red_false_alarm": RED_FALSE_ALARM, "yellow_false_alarm": YELLOW_FALSE_ALARM},
    }
    print(json.dumps(result["test"], indent=1))
    RESULTS_PATH.write_text(json.dumps(result, indent=2))
    print(f"results: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
