"""Patch classifier inference with ONNX Runtime (TDD 3.1 step 4, 5.2).

Loads the organ's model exported in step 3 (pipeline/organs.py: engine/model/model_fp32.onnx
for lymph node or TRIAGE_MODEL_PATH, engine/model/<organ>/model_fp32.onnx otherwise) and
returns P_malignant per patch. ONNX graph contract (see engine/README.md):
  input  float32 (N, 3, S, S), RGB in [0, 1]    output  float32 (N,), P_malignant in [0, 1]

Execution providers are tried in order DirectML -> OpenVINO -> CPU; only those included in
the installed onnxruntime build are available (onnxruntime-directml / onnxruntime-openvino).
onnxruntime is imported on first use, so a missing install fails the slide with a clear
error instead of making the engine unimportable (the backend would then silently fall back
to its stub scorer).
"""
import functools
import logging
import threading
from pathlib import Path

import cv2
import numpy as np

from .organs import get_organ

log = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "model_fp32.onnx"  # lymph node
PREFERRED_PROVIDERS = ("DmlExecutionProvider", "OpenVINOExecutionProvider", "CPUExecutionProvider")
BATCH_SIZE = 16  # TDD 5.2: dynamic batching, N = 8 or 16


def model_path(organ: str = None) -> Path:
    """The organ's model file (None = the default organ). Raises ValueError for an unknown organ."""
    return get_organ(organ).model_path


def _create_session(path: Path, providers, threads: int):
    """InferenceSession on the first provider that loads, with CPU as the last resort."""
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    errors = []
    for provider in [p for p in providers if p in available]:
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        if provider == "DmlExecutionProvider":  # required by DirectML
            options.enable_mem_pattern = False
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        try:
            fallback = [] if provider == "CPUExecutionProvider" else ["CPUExecutionProvider"]
            return ort.InferenceSession(str(path), options, providers=[provider, *fallback])
        except Exception as exc:  # e.g. a GPU driver problem: try the next provider
            log.warning("could not start ONNX Runtime with %s: %s", provider, exc)
            errors.append(f"{provider}: {exc}")
    raise RuntimeError(f"no usable ONNX Runtime provider for {path}: {errors or 'none installed'}")


class PatchClassifier:
    """Scores RGB uint8 patches; resizes them to the model's input size if they differ."""

    def __init__(self, path: Path, providers=PREFERRED_PROVIDERS, threads: int = 0, batch_size: int = BATCH_SIZE):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"AI model not found at {path}. Train and export it (engine/README.md, "
                "'Training the patch classifier'), copy model_fp32.onnx there, or set TRIAGE_MODEL_PATH."
            )
        self.session = _create_session(path, providers, threads)
        self.provider = self.session.get_providers()[0]
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        self.output_name = self.session.get_outputs()[0].name
        self.input_size = int(model_input.shape[2])
        self.batch_size = batch_size
        log.info("AI model %s loaded on %s (input %d px)", path.name, self.provider, self.input_size)

    def _prepare(self, patches: np.ndarray) -> np.ndarray:
        """uint8 (N, H, W, 3) RGB -> float32 (N, 3, S, S) in [0, 1]."""
        if patches.shape[1:3] != (self.input_size, self.input_size):
            shrink = patches.shape[1] > self.input_size
            size = (self.input_size, self.input_size)
            interpolation = cv2.INTER_AREA if shrink else cv2.INTER_LINEAR
            patches = np.stack([cv2.resize(p, size, interpolation=interpolation) for p in patches])
        return np.ascontiguousarray(patches.transpose(0, 3, 1, 2), dtype=np.float32) / 255.0

    def predict(self, patches: np.ndarray) -> np.ndarray:
        """P_malignant for each patch, float32 (N,)."""
        if patches.ndim != 4 or patches.shape[3] != 3:
            raise ValueError(f"expected RGB patches of shape (N, H, W, 3), got {patches.shape}")
        if len(patches) == 0:
            return np.zeros(0, dtype=np.float32)
        probs = []
        for start in range(0, len(patches), self.batch_size):
            x = self._prepare(patches[start:start + self.batch_size])
            probs.append(self.session.run([self.output_name], {self.input_name: x})[0])
        probs = np.concatenate(probs).astype(np.float32).reshape(-1)
        if probs.shape != (len(patches),) or not np.all((probs >= 0.0) & (probs <= 1.0)):
            raise RuntimeError("model output is not one probability in [0, 1] per patch")
        return probs


_load_lock = threading.Lock()


@functools.lru_cache(maxsize=8)
def _cached_classifier(path: Path) -> PatchClassifier:
    return PatchClassifier(path)


def get_classifier(organ: str = None) -> PatchClassifier:
    """The shared classifier for the organ's model, loaded once (the backend may call from threads)."""
    path = model_path(organ)
    with _load_lock:
        return _cached_classifier(path)
