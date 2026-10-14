"""One AI model per organ (issue #53).

Each organ's model is trained on that organ's tissue only (the lymph-node model flags 20-50%
of normal patches from other organs on PLISM), so the slide's organ chooses the model.
Everything that belongs to one model lives in its OrganModel: the ONNX file, the model card,
the training magnification (µm/px) and the slide-score settings and flag thresholds tuned
on that model's scores (training/tune_scoring.py).

The lymph-node model keeps its original place, engine/model/model_fp32.onnx (the backend's
packaging and the start scripts expect it there). Other organs live in engine/model/<organ>/.
Add an organ here once its model is trained, tuned and its card generated.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from . import scale, scoring

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
MODEL_FILE = "model_fp32.onnx"
CARD_FILE = "model_card.json"
DEFAULT_ORGAN = "lymph_node"


@dataclass(frozen=True)
class OrganModel:
    organ: str
    folder: Path
    um_per_px: float  # magnification the model was trained at; captures are resized to it
    red: float
    yellow: float
    top_k: int = scoring.TOP_K
    w_max: float = scoring.W_MAX

    @property
    def model_path(self) -> Path:
        # TRIAGE_MODEL_PATH replaces the default organ's model only (tests, custom builds).
        override = os.getenv("TRIAGE_MODEL_PATH") if self.organ == DEFAULT_ORGAN else None
        return Path(override or self.folder / MODEL_FILE)

    @property
    def card_path(self) -> Path:
        return self.folder / CARD_FILE


ORGANS = {
    DEFAULT_ORGAN: OrganModel(
        DEFAULT_ORGAN, MODEL_DIR, scale.MODEL_UM_PER_PX, scoring.RED_THRESHOLD, scoring.YELLOW_THRESHOLD
    ),
    # NCT-CRC-HE tiles are 0.5 µm/px. Settings from training/results/slide_scoring_colon.json:
    # the search preferred the single highest tile (top_k = 1).
    "colon": OrganModel("colon", MODEL_DIR / "colon", um_per_px=0.5, red=0.54, yellow=0.50, top_k=1, w_max=0.0),
}


def get_organ(organ: str = None) -> OrganModel:
    """The organ's model settings; None means DEFAULT_ORGAN. Raises ValueError for an unknown organ."""
    name = DEFAULT_ORGAN if organ is None else organ
    try:
        return ORGANS[name]
    except (KeyError, TypeError):
        raise ValueError(f"no AI model for organ {organ!r}; available: {sorted(ORGANS)}") from None


def available_organs() -> list:
    """Organs whose model file is present, default first (for the organ picker)."""
    return [name for name, spec in ORGANS.items() if spec.model_path.is_file()]
