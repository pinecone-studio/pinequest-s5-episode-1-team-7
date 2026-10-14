"""What AI is scoring the slides (About the AI): the engine's model card plus live status."""
from fastapi import APIRouter, HTTPException

from ..engine_adapter import get_model_info

router = APIRouter(tags=["model"])


@router.get("/model")
def get_model():
    """The committed model card (identity, training, metrics, limitations) with the
    live model file (name, SHA-256, matches-card) and ONNX provider in use."""
    info = get_model_info()
    if info is None:
        raise HTTPException(503, "AI engine model info unavailable")
    return info
