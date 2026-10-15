"""Contract between the backend (Member 2) and the AI engine (Member 1) - see docs/PLAN.md.

Member 1 exposes ONE function (default TRIAGE_ENGINE="engine.pipeline:analyze_slide"):

    def analyze_slide(image_path: str, um_per_px: float | None = None, organ: str | None = None) -> dict:
        return {
            "score": 0.83,                 # S_slide in [0, 1]            (required)
            "risk_flag": "red",            # "red" | "yellow" | "green"   (optional)
            "heatmap_path": "/tmp/h.png",  # PNG overlay, backend moves it (optional)
            "num_patches": 142,            # (optional)
            "inference_ms": 1180.0,        # (optional)
            "um_per_px_used": 0.25,        # µm/px the photo was taken at, None if not given (optional)
            "scale_warning": None,         # e.g. "no_scale_info" when um_per_px was None (optional)
            "organ": "colon",              # organ whose model scored it (optional)
        }

`um_per_px` is the photo's microns per pixel from the backend's calibrated setup
profile (issue #35); the engine resizes to that organ model's training scale
(0.42 µm/px for lymph node, 0.5 for colon) before tiling, and the heatmap keeps
the original photo's size. Values outside 0.05-2.0 µm/px raise ValueError
(almost certainly a calibration or objective mistake), so the slide is marked
FAILED. `organ` picks the organ's model (issue #53); None means the default
organ and there is no fallback to another organ's model — an unknown organ
raises ValueError. Engines that only take `image_path` keep working: the
backend passes `um_per_px`/`organ` only when the entry point accepts them
(see call_engine).

If `risk_flag` is omitted the backend derives it from config thresholds.
Until the engine exists (or if it fails to import) a deterministic STUB is used so the whole
pipeline can be demoed. The stub is NOT a real model.

Member 1 also exposes `model_info(organ=None) -> dict` (About the AI): the organ's
committed model card plus the live model file (name, SHA-256, whether it matches
the card) and the ONNX execution provider in use. `GET /model` serves it (per
organ); every scored slide stores organ + model name + hash (stub scores are
labelled `model_name="stub"`). Engines without `model_info` get `GET /model` 503.
`available_organs()` lists organs whose model file is present, default first.
"""
import functools
import importlib
import inspect
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
    um_per_px_used: Optional[float] = None
    scale_warning: Optional[str] = None
    organ: Optional[str] = None

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
        um_per_px_used = raw.get("um_per_px_used")
        if um_per_px_used is not None:
            try:
                um_per_px_used = float(um_per_px_used)
            except (TypeError, ValueError) as exc:
                raise ValueError("engine 'um_per_px_used' is not a number") from exc
            if not math.isfinite(um_per_px_used) or um_per_px_used <= 0:
                raise ValueError(f"engine 'um_per_px_used' must be positive, got {um_per_px_used}")
        scale_warning = raw.get("scale_warning")
        if scale_warning is not None:
            scale_warning = str(scale_warning)
        organ = raw.get("organ")
        if organ is not None:
            organ = str(organ)
        return cls(
            score=score,
            risk_flag=flag,
            heatmap_path=str(raw["heatmap_path"]) if raw.get("heatmap_path") else None,
            num_patches=int(num_patches) if num_patches is not None else None,
            inference_ms=float(inference_ms) if inference_ms is not None else None,
            um_per_px_used=um_per_px_used,
            scale_warning=scale_warning,
            organ=organ,
        )


def call_engine(fn: AnalyzeFn, image_path: str, um_per_px: Optional[float] = None,
                organ: Optional[str] = None) -> dict:
    """Call the engine entry point, passing um_per_px/organ when accepted.

    Old engines and test doubles that only take image_path keep working: each
    keyword is passed only when the signature has that parameter (issue #53).
    """
    kwargs: dict = {}
    if um_per_px is not None or organ is not None:
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            params = {}
        if um_per_px is not None and "um_per_px" in params:
            kwargs["um_per_px"] = um_per_px
        if organ is not None and "organ" in params:
            kwargs["organ"] = organ
    return fn(image_path, **kwargs)


def _ensure_repo_root() -> None:
    """Make the sibling engine/ package importable (backend/app/ -> repo root)."""
    try:
        repo_root = str(Path(__file__).resolve().parents[2])
        if repo_root not in sys.path:
            sys.path.append(repo_root)
    except IndexError:  # frozen executable layout
        pass


def get_model_info(organ: Optional[str] = None) -> Optional[dict]:
    """The organ model's card plus live file/provider status (About the AI).

    Returns None when the engine cannot be imported or predates model_info()
    (the stub has no model to describe). Never raises.
    """
    try:
        _ensure_repo_root()
        module_name, _ = config.ENGINE_ENTRYPOINT.split(":")
        fn = getattr(importlib.import_module(module_name), "model_info", None)
        if not callable(fn):
            return None
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            params = {}
        info = fn(organ=organ) if "organ" in params else fn()
        return info if isinstance(info, dict) else None
    except Exception:
        return None


def available_organs() -> list:
    """Organs with a model file present, default first (for the organ picker).

    Empty when the engine cannot be imported: the caller falls back to the
    default organ instead of offering nothing.
    """
    try:
        _ensure_repo_root()
        module_name, _ = config.ENGINE_ENTRYPOINT.split(":")
        fn = getattr(importlib.import_module(module_name), "available_organs", None)
        if not callable(fn):
            return []
        organs = fn()
        return list(organs) if organs else []
    except Exception:
        return []


def default_organ() -> str:
    """The organ used when none is picked (old slides, plain API calls)."""
    try:
        _ensure_repo_root()
        module_name, _ = config.ENGINE_ENTRYPOINT.split(":")
        return str(getattr(importlib.import_module(module_name), "DEFAULT_ORGAN", "lymph_node"))
    except Exception:
        return "lymph_node"


def _stub_analyze_slide(image_path: str, um_per_px: Optional[float] = None) -> dict:
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
        "um_per_px_used": um_per_px,
        "scale_warning": None if um_per_px is not None else "no_scale_info",
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
