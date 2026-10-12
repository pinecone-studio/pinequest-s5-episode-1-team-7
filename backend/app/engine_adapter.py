"""Contract between the backend (Member 2) and the AI engine (Member 1) - see docs/PLAN.md.

Member 1 exposes ONE function (default TRIAGE_ENGINE="engine.pipeline:analyze_slide"):

    def analyze_slide(image_path: str) -> dict:
        return {
            "score": 0.83,                 # S_slide in [0, 1]            (required)
            "risk_flag": "red",            # "red" | "yellow" | "green"   (optional)
            "heatmap_path": "/tmp/h.png",  # PNG overlay, backend moves it (optional)
            "num_patches": 142,            # (optional)
            "inference_ms": 1180.0,        # (optional)
        }

If `risk_flag` is omitted the backend derives it from config thresholds.
Until the engine exists (or if it fails to import) a deterministic STUB is used so the whole
pipeline can be demoed. The stub is NOT a real model.
"""
import functools
import importlib
import logging
import math
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import cv2
import numpy as np

from . import config

log = logging.getLogger(__name__)
FLAGS = {"red", "yellow", "green"}
AnalyzeFn = Callable[[str], dict]


@dataclass
class AnalysisResult:
    score: float
    risk_flag: Optional[str] = None
    heatmap_path: Optional[str] = None
    num_patches: Optional[int] = None
    inference_ms: Optional[float] = None

    @classmethod
    def from_dict(cls, raw: Any) -> "AnalysisResult":
        """Validate whatever the engine returned. Raises ValueError on contract violations."""
        if not isinstance(raw, dict) or "score" not in raw:
            raise ValueError("engine must return a dict containing 'score'")
        try:
            score = float(raw["score"])
        except (TypeError, ValueError) as exc:
            raise ValueError("engine 'score' is not a number") from exc
        if math.isnan(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"engine 'score' must be within [0, 1], got {score}")
        flag = raw.get("risk_flag")
        if flag is not None:
            flag = str(flag).lower()
            if flag not in FLAGS:
                raise ValueError(f"engine 'risk_flag' must be one of {sorted(FLAGS)}, got {flag!r}")
        num_patches = raw.get("num_patches")
        inference_ms = raw.get("inference_ms")
        return cls(
            score=score,
            risk_flag=flag,
            heatmap_path=str(raw["heatmap_path"]) if raw.get("heatmap_path") else None,
            num_patches=int(num_patches) if num_patches is not None else None,
            inference_ms=float(inference_ms) if inference_ms is not None else None,
        )


def _stub_analyze_slide(image_path: str) -> dict:
    """Placeholder scorer: more saturated (stained) tissue -> higher 'risk'."""
    t0 = time.perf_counter()
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("cannot decode image")
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32) / 255.0
    config.HEATMAPS_DIR.mkdir(parents=True, exist_ok=True)
    heatmap = config.HEATMAPS_DIR / f"stub-{uuid.uuid4().hex}.png"
    cv2.imwrite(str(heatmap), cv2.applyColorMap((sat * 255).astype(np.uint8), cv2.COLORMAP_JET))
    return {
        "score": float(np.clip(sat.mean() * 1.5, 0.0, 1.0)),
        "heatmap_path": str(heatmap),
        "num_patches": 1,
        "inference_ms": (time.perf_counter() - t0) * 1000.0,
    }


@functools.lru_cache(maxsize=1)
def load_engine() -> AnalyzeFn:
    """Import the engine entry point; fall back to the stub (with a warning) if that is impossible."""
    try:
        repo_root = str(Path(__file__).resolve().parents[2])  # backend/app/ -> repo root (sibling engine/)
        if repo_root not in sys.path:
            sys.path.append(repo_root)
    except IndexError:  # frozen executable layout
        pass
    try:
        module_name, func_name = config.ENGINE_ENTRYPOINT.split(":")
        fn = getattr(importlib.import_module(module_name), func_name)
        log.info("AI engine loaded: %s", config.ENGINE_ENTRYPOINT)
        return fn
    except Exception as exc:
        log.warning("Could not load engine %r (%s) - using STUB scorer", config.ENGINE_ENTRYPOINT, exc)
        return _stub_analyze_slide
