"""What AI is scoring the slides (About the AI): the engine's model card plus live status."""
from fastapi import APIRouter, HTTPException

from ..engine_adapter import available_organs, get_model_info

router = APIRouter(tags=["model"])


@router.get("/model")
def get_model(organ: str | None = None):
    """The organ model's committed card (identity, training, metrics, limitations)
    with the live model file (name, SHA-256, matches-card) and ONNX provider in use."""
    if organ is not None:
        known = available_organs()
        if known and organ not in known:
            raise HTTPException(404, f"no AI model for organ {organ!r}")
    info = get_model_info(organ)
    if info is None:
        raise HTTPException(503, "AI engine model info unavailable")
    return info
