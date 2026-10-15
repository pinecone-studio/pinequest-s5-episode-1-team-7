"""Organs with a trained model (issue #53): the UI offers only these in its picker."""
from fastapi import APIRouter

from ..engine_adapter import available_organs, default_organ

router = APIRouter(tags=["organs"])


@router.get("/organs")
def list_organs():
    """Organ keys with a model file present, default first. Falls back to the
    default organ when the engine is unavailable, so the picker never empties."""
    organs = available_organs()
    if organs:
        return organs
    return [default_organ()]
