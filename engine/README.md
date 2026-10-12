# AI Inference & Heatmap Engine

Owner: Member 1 (ML / AI Engine). See [../docs/PLAN.md](../docs/PLAN.md) for the step-by-step plan.

## Layout
- `pipeline/`: tiling, background masking, inference, scoring, heatmaps
- `model/`: ONNX model files (FP32 / INT8), not committed
- `training/`: fine-tuning and ONNX export scripts
- `tests/`: pytest tests

## Setup
Requires Python 3.11+.

```bash
cd engine
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # runtime + tests
pip install -r requirements-train.txt    # only if training/exporting models
pytest
```
