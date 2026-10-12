from pathlib import Path

import pytest

TINY_MODEL = Path(__file__).parent / "fixtures" / "tiny_model.onnx"


@pytest.fixture(autouse=True)
def tiny_model(monkeypatch):
    """Run every test against the tiny fixture model, never the real (untracked) one."""
    monkeypatch.setenv("TRIAGE_MODEL_PATH", str(TINY_MODEL))
    return TINY_MODEL
