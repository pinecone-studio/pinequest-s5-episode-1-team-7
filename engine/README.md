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

## Training the patch classifier (step 3)
Dataset: [PatchCamelyon (PCam)](https://github.com/basveeling/pcam), 327,680 H&E patches (96×96) of lymph node sections labelled tumour / no tumour. License: CC0, so trained weights can be redistributed.

Run everything from `engine/`. For GPU training, install the CUDA build of PyTorch first (see the comment in `requirements-train.txt`).

```bash
python -m training.download_pcam      # ~7.6 GB download -> data/pcam/*.h5 (~9 GB)
python -m training.train --limit 4096 --epochs 1   # smoke test
python -m training.train              # MobileNetV3-Small, 224 px, 8 epochs (~25 min on an RTX 4060)
python -m training.export_onnx --results training/results/pcam_mobilenet_v3_small_224.json
```

`data/` can be a link to another drive (e.g. `mklink /J data B:\pinequest-data` on Windows).

- `train.py` trains with strong augmentation (rotations, zoom, H&E stain jitter, lighting, blur, noise) and an EMA of the weights, keeps the epoch with the best validation AUC (`model/pcam_<arch>_<size>.pt`), then evaluates it once on the test split, with and without 8-view test-time augmentation (TTA). Metrics go to `training/results/` (committed).
- `--img-size 96` trains at PCam's native size (5x faster, lower AUC); `--arch resnet18` trains the fallback model.
- `export_onnx.py` writes `model/model_fp32.onnx` and fails if its output differs from PyTorch. `--tta N` bakes N-view TTA into the graph (N times slower).
- Don't edit `training/*.py` during a run: on Windows the data-loader workers re-import the code when they start.

### Results (PCam test split, 32,768 patches)
| Run | Test AUC | Accuracy | CPU time / slide* |
|---|---|---|---|
| 96 px, light augmentation (first run) | 0.919 | 81.2% | 0.06 s |
| 96 px, strong augmentation + EMA | 0.922 | 78.5% | 0.06 s |
| 96 px, + 8-view TTA | 0.933 | 79.1% | 0.50 s |
| **224 px, strong augmentation + EMA (shipped)** | **0.960** | **86.0%** | **0.29 s** |
| 224 px, + 8-view TTA | 0.964 | 85.9% | 2.03 s |

\*150 tissue patches (a typical 12 MP capture), ONNX Runtime FP32, 4 threads of an i5-13400F. The TDD target is < 1.5 s on an i3-class CPU, so 8-view TTA at 224 px is too slow; revisit after INT8 quantisation (step 4).

At a 0.5 threshold the shipped model catches 74% of tumour patches (specificity 98%). A threshold chosen on validation for 90% sensitivity (≈ 0.13) gives 86% sensitivity / 93% specificity on test. The real threshold is for the team to decide in step 6.

ONNX contract for the inference runner (step 5):
- input `patches`: float32 `(N, 3, S, S)`, RGB in [0, 1]; `S` is the model's `input_size` metadata (224 for the shipped model, the same as the pipeline's tile size)
- output `p_malignant`: float32 `(N,)` in [0, 1]
- ImageNet normalisation and the sigmoid are inside the graph

## Inference (step 5)
`pipeline/inference.py` runs the exported model inside `analyze_slide()`:
- Model: `model/model_fp32.onnx`, or the file in `TRIAGE_MODEL_PATH`. It is not in git, so get it from a teammate or train and export it as above. **If it is missing, `analyze_slide` raises `FileNotFoundError`** and the backend marks the slide FAILED with that message. There is no silent fallback to fake scores.
- Execution providers are tried in the order DirectML → OpenVINO → CPU. Only the providers in the installed onnxruntime build are tried (`onnxruntime-directml` or `onnxruntime-openvino`); plain `onnxruntime` is CPU only.
- Patches are scored in batches of 16 and resized to the model's input size if they differ.
- onnxruntime is imported on first use. `backend/requirements.txt` must include it (step 8, coordinate with the backend owner); without it, every slide fails with `No module named 'onnxruntime'`.
- Tests use `tests/fixtures/tiny_model.onnx` (449 bytes, same contract), so they need neither torch nor the real model.

A 12 MP capture (~200 tissue patches) takes about 0.6 s end to end on CPU (i5-13400F), including tiling, masking and the heatmap.

Caveat: PCam is scanner images of lymph node metastases at ~10× magnification, and the model sees them upsampled 2.3×. Smartphone-through-eyepiece captures look different (colour, blur, magnification), so expect accuracy on real captures to be lower than the PCam test score until we fine-tune on our own images.
