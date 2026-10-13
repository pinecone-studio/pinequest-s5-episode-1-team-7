# AI Inference & Heatmap Engine

Owner: Member 1 (ML / AI Engine). See [../docs/PLAN.md](../docs/PLAN.md) for the step-by-step plan.

## Layout
- `pipeline/`: tiling, background masking, inference, scoring, heatmaps
- `model/`: ONNX model files. `model_fp32.onnx` (the runtime model) is committed; INT8 and training checkpoints are not
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

## INT8 quantization (step 4)
```bash
python -m training.quantize     # model/model_fp32.onnx -> model/model_int8.onnx, plus an FP32 vs INT8 report
```
Static QDQ quantization of the Conv and Gemm layers, calibrated on 512 PCam training patches. The first 10 convolutions stay FP32 (`--fp32-convs`): in MobileNetV3 a few channels of the first conv are far larger than the rest, so a shared 8-bit scale wipes out the small channels and the following depthwise conv amplifies the error. Weights use reduce-range (7-bit) so CPUs without VNNI, such as the TDD's 8th-gen i3, don't hit ONNX Runtime's U8S8 saturation issue.

| Model (PCam test split) | Test AUC | Size | CPU time / slide* |
|---|---|---|---|
| FP32 | 0.960 | 6.4 MB | 0.10 s |
| **INT8, first 10 convs FP32** | **0.963** | **1.8 MB (−72%)** | 0.15 s |
| INT8, every conv quantized | 0.582 | 1.8 MB | 0.20 s |

\*Median of 5 runs after warm-up (the step 3 table above timed one cold run), same 150 patches and 4 threads.

INT8 keeps accuracy and is 72% smaller, but it is **slower** than FP32: MobileNetV3-Small is so small that the extra quantize/dequantize steps cost more than the 8-bit maths saves. Use `model_fp32.onnx` at runtime; `model_int8.onnx` only helps where file size matters. INT8 does pay off for bigger models: ResNet-18 went from 1.29 s / 44.8 MB to 0.43 s / 11.4 MB with near-identical outputs, but that is still slower than MobileNetV3-Small in FP32.

## Inference (step 5)
`pipeline/inference.py` runs the exported model inside `analyze_slide()`:
- Model: `model/model_fp32.onnx`, or the file in `TRIAGE_MODEL_PATH`. It is committed (6.4 MB, MobileNetV3-Small at 224 px, PCam test AUC 0.960); re-export it as above after retraining. **If it is missing, `analyze_slide` raises `FileNotFoundError`** and the backend marks the slide FAILED with that message. There is no silent fallback to fake scores.
- Execution providers are tried in the order DirectML → OpenVINO → CPU. Only the providers in the installed onnxruntime build are tried (`onnxruntime-directml` or `onnxruntime-openvino`); plain `onnxruntime` is CPU only.
- Patches are scored in batches of 16 and resized to the model's input size if they differ.
- onnxruntime is imported on first use. `backend/requirements.txt` must include it (step 8, coordinate with the backend owner); without it, every slide fails with `No module named 'onnxruntime'`.
- Tests use `tests/fixtures/tiny_model.onnx` (449 bytes, same contract), so they need neither torch nor the real model.

A 12 MP capture (~200 tissue patches) takes about 0.6 s end to end on CPU (i5-13400F), including tiling, masking and the heatmap.

## Slide score and risk flag (step 6)
`pipeline/scoring.py` turns the patch probabilities into one score and a flag:

```
z       = W_MAX · max(logit P) + (1 − W_MAX) · mean(top-K logit P)     W_MAX = 0, K = 3
S_slide = sigmoid(z / 4)                                                red ≥ 0.82, yellow ≥ 0.72
```

- The formula is the TDD's, applied to patch log-odds rather than probabilities. The model is so confident that probability-space scores crowd just below 1.0 (thresholds would sit at 0.99x and slides would tie).
- `analyze_slide` now returns `risk_flag` too, so the backend's `TRIAGE_RED` / `TRIAGE_YELLOW` defaults are no longer used: the thresholds belong to this model's score scale.
- `python -m training.tune_scoring` chose W_MAX, K and the thresholds on slides simulated from PCam validation patches. Normal slides have 50–250 normal patches; tumour slides have 1–50% tumour patches. Red is set to catch 5% of normal validation slides, and yellow-or-red 25%.

Test split, 2,000 simulated slides per row:

| Slide | Slide AUC | Flagged red | Flagged yellow or red |
|---|---|---|---|
| Normal | – | 0.0% | 3.0% |
| 1% tumour | 0.745 | 3.7% | 27.7% |
| 2% tumour | 0.857 | 17.3% | 53.3% |
| 5% tumour | 0.969 | 56.9% | 86.3% |
| 10% tumour | 0.997 | 86.4% | 98.1% |
| 25% tumour | 1.000 | 99.1% | 99.95% |

The old `max(P)` rule scored a normal PCam-built slide 0.995 against 1.000 for tumour. The new score gives 0.69 (green) against 0.95 (red), and 0.88 (red) for a slide with 5% tumour.

Limits: patches are sampled independently, which ignores within-slide correlation (stain, focus), and PCam's validation and test splits differ (normal slides flagged yellow or red: 25% on validation, 3% on test). Re-tune on real smartphone captures before relying on the thresholds.

## Heatmap overlay (step 7)
`pipeline/heatmap.py` writes an RGBA PNG the size of the photo, for the viewer's overlay:
- **Colour:** patch P_malignant, green 0 → yellow 0.5 → red 1. It is interpolated between the centres of scored tiles, so the overlay is smooth rather than blocky, and unscored background tiles don't pull it towards green.
- **Alpha:** only tissue pixels of scored tiles are opaque, using the tissue mask from step 2. White background and fat holes stay clear. The UI applies the opacity slider.
- **Hotspots:** tiles with P ≥ 0.8 are outlined in bright cyan, clipped to tissue and with adjacent tiles merged, ignoring specks under a quarter tile (TDD 6.2 focus cues). The outline is part of the same PNG, so it fades with the opacity slider too.

A 12 MP capture takes ~0.45 s for the heatmap and ~0.9 s for the whole `analyze_slide` (i5-13400F). Grad-CAM is not implemented: it needs gradients, meaning PyTorch (~2 GB) or a second gradient model on the clinic PC, and the patch map already shows where to look at tile resolution.

## Distillation from a pathology foundation model
A large pathology foundation model is a much better patch classifier but far too slow for a clinic CPU. Distillation trains the same 6 MB MobileNetV3 to imitate it, so the runtime is unchanged.

1. **Teacher:** [Hibou-B](https://huggingface.co/histai/hibou-b) (Apache 2.0, ViT-B/14, 86M parameters), frozen, plus a linear head trained on its PCam features (`training/teacher.py`). Its weights load into transformers' built-in `Dinov2WithRegistersModel`, so no code from the model repository is executed.
2. **Student:** `train.py --teacher hibou-b`. The loss is half true labels and half the teacher's probability for the clean image, softened with temperature 2. The student sees augmented copies, so it also learns to give a recoloured or blurred image the teacher's answer for the clean one.

```bash
# once: accept the terms on huggingface.co/histai/hibou-b, then log in with a Read token
hf auth login
# optional: keep the ~350 MB download off a full drive (PowerShell: $env:HF_HUB_CACHE = "B:\...")
export HF_HUB_CACHE=/path/with/space/hf-cache/hub
python -m training.teacher --teacher hibou-b              # features (~15 min on an RTX 4060, cached) + head
python -m training.train --teacher hibou-b --tag kd-hibou   # ~25 min
python -m training.export_onnx --checkpoint model/pcam_mobilenet_v3_small_224_kd-hibou.pt \
    --out model/model_fp32_kd-hibou.onnx --results training/results/pcam_mobilenet_v3_small_224_kd-hibou.json
```

| PCam test split | AUC | Accuracy | Sensitivity | Specificity | Size |
|---|---|---|---|---|---|
| Hibou-B teacher (linear head) | 0.984 | 94.3% | – | – | 350 MB |
| **Distilled student** | **0.969** | **87.8%** | **77.3%** | **98.2%** | **6 MB** |
| Current model (no teacher) | 0.960 | 86.0% | 74.0% | 97.9% | 6 MB |

The student recovers 37% of the AUC gap to the teacher, which is typical for distillation into a model this much smaller. This is a single run; PCam varies by roughly ±0.003–0.005 AUC between seeds. Shipping the student means replacing `model/model_fp32.onnx` **and re-running `training.tune_scoring`**, because the step 6 thresholds depend on the model's score distribution.

## Robustness on smartphone captures (PLISM)
`training/plism_eval.py` scores [PLISM-sm](https://doi.org/10.25452/figshare.plus.c.6773925) (CC BY 4.0): the same tissue spots imaged by 7 slide scanners and 6 smartphones through a microscope eyepiece. For each device it reports false alarms on normal lymph node, malignant-versus-normal separation, agreement with a reference scanner, and sharpness. The images are ~0.45 µm/px, close to the model's training scale. Download instructions are in the script's docstring.

Caveat: PCam is scanner images of lymph node metastases at ~10× magnification, and the model sees them upsampled 2.3×. Smartphone-through-eyepiece captures look different (colour, blur, magnification), so expect accuracy on real captures to be lower than the PCam test score until we fine-tune on our own images.
