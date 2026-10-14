# Project Plan — AI Pathology Triage System

Source of truth: [TDD.md](TDD.md). This plan splits the TDD across the team and breaks each role into small, separately reviewable steps (one step ≈ one PR).

## Team split

| Member | Role | Owns (folder) | TDD sections |
|---|---|---|---|
| 1 | ML / AI Engine Engineer | `engine/` | 2.3, 5.2, 3.1 (steps 3, 4, 5, 7) |
| 2 | Backend & System Integration | `backend/` | 2.1, 2.2 (Backend), 3.1 (steps 1, 2, 6), 3.2 |
| 3 | Front-End UI/UX & Packaging | `frontend/` | 2.2 (Front-End), 6.1, 6.2, 7.2, 8.1 / 8.2 |

Rule: each member changes only their own folder. Cross-folder changes go through the interface contract below.

---

## Member 1 — ML / AI Engine (`engine/`)

Work through these in order. Finish, test and merge each step before starting the next.

### Step 0 — Engine project setup ✅ (#5)
- `engine/` as a Python 3.11 package: `engine/pipeline/`, `engine/model/`, `engine/tests/`.
- `engine/requirements.txt`: `numpy`, `opencv-python-headless`, `onnxruntime`, `pytest` (training extras such as `torch` and `torchvision` go in a separate `requirements-train.txt`).
- Done when `pytest engine/tests` runs.

> **Import rule:** the backend imports the engine as `engine.pipeline`, while engine tests import it as `pipeline`. Inside `engine/pipeline/`, always use relative imports (`from .tiling import ...`) so both work.

### Step 1 — Image tiling (TDD 3.1 step 3) ✅ (#15)
- `pipeline/tiling.py`: split a high-res image into 224×224 patches, keeping each patch's (row, col) position for the heatmap later.
- Handle edges (pad or drop partial tiles; decide and document).
- Tests: tile count and coordinates for known image sizes.

### Step 2 — Background masking (TDD 5.2, 3.1 step 3, 8.1) ✅ (#16)
- `pipeline/masking.py`:
  - Otsu threshold on grayscale → tissue mask.
  - RGB→HSV saturation filter to drop blank and white background.
  - Tissue fraction per patch; drop patches below a threshold (e.g. < 50% tissue).
- Optional CLAHE for uneven lighting (TDD 8.1).
- Tests: a blank image gives 0 patches; a synthetic "tissue" region is kept.

### Step 2b — End-to-end skeleton (no model yet) ✅ (#17)
Get the whole system running early, before the model exists.
- `analyze_slide(image_path)` in `engine/pipeline/__init__.py`, the entry point the backend loads (`engine.pipeline:analyze_slide`).
- Uses the real tiling and masking from Steps 1–2, with a **placeholder** per-patch score (e.g. stain saturation) and a simple patch heatmap PNG.
- Returns the contract dict (see Step 8). From then on the backend uses it instead of its built-in stub.
- Done when an image uploaded through the backend's `/ingest` gets a score and a heatmap from the engine.
- Steps 3–7 then replace the placeholder pieces one at a time, without changing the contract.

### Step 3 — Model setup and ONNX export (TDD 2.3, 4) ✅ (#18; model committed in #24)
- Start from pretrained MobileNetV3-Small (fallback: ResNet-18) with a binary head (benign / malignant).
- Fine-tune on a public histopathology dataset (e.g. PCam or BreakHis); keep the training script in `engine/training/`.
- Export to `engine/model/model_fp32.onnx`. Record accuracy / AUC on a held-out set.
- Result (PCam, MobileNetV3-Small, 224 px, strong augmentation + EMA): test AUC 0.960, accuracy 86.0%, 0.29 s CPU per slide (FP32). The first 96 px run scored AUC 0.919. Details in `engine/README.md` and `engine/training/results/`.

### Step 4 — INT8 quantization (TDD 5.2) ✅ (#19)
- `onnxruntime.quantization.quantize_static` with a small calibration set → `model_int8.onnx`.
- Compare FP32 and INT8 size (target about 75% smaller), AUC drop, and CPU latency. Target: under 1.5 s per slide.
- Result: INT8 (first 10 convs kept FP32) is 72% smaller (1.8 MB) with no AUC loss (0.963), but slower than FP32 on CPU (0.15 s vs 0.10 s per slide), because MobileNetV3-Small is too small to gain from INT8. Fully quantized, AUC collapses to 0.58. **Decision: the runtime uses `model_fp32.onnx`**, which already meets the 1.5 s target with a wide margin. Details in `engine/README.md`.

### Step 5 — Inference runner (TDD 3.1 step 4, 5.2) ✅ (#20)
- `pipeline/inference.py`: load the ONNX session with provider fallback (DirectML / OpenVINO → CPU).
- Dynamic batching (N = 8 or 16) → `P_malignant ∈ [0,1]` per patch.
- Done: `analyze_slide` now uses the real model (batches of 16; DirectML → OpenVINO → CPU). A missing model raises a clear error instead of returning fake scores. Finding for step 6: the interim `max(P_patch)` slide score cannot separate slides. A slide built from normal PCam patches scored 0.995 against 1.000 for tumour, because about 2% of normal patches score high. The top-10% mean gave 0.36 vs 1.00, and the mean gave 0.04 vs 0.70.

### Step 6 — Slide-level score (TDD 3.1 step 5) ✅ (#22; values await team sign-off)
- `pipeline/scoring.py`: `S_slide = w1 · max(P_patch) + w2 · mean(top-k P_patch)`.
- Map S_slide to a Red / Yellow / Green risk flag (thresholds to agree with Member 3).
- Tests: known probability arrays → expected score and flag.
- Done: the formula is applied to patch log-odds, with w1 = 0 and k = 3 (the mean of the 3 highest patch log-odds), and S = sigmoid(z / 4). Red ≥ 0.82, yellow ≥ 0.72. All were chosen on slides simulated from PCam validation patches (`engine/training/tune_scoring.py`). On test, 0% of normal slides are flagged red and 3% yellow; slides with 5% tumour are flagged yellow or red 86% of the time, and slides with 10% tumour 98%. `analyze_slide` now returns `risk_flag`, so the backend's thresholds are no longer used. Details in `engine/README.md`. Re-tune on real captures.
- Update: the shipped model is now the Hibou-B-distilled student (PCam test AUC 0.969), and the thresholds were re-tuned for it to **red ≥ 0.81, yellow ≥ 0.70**. With 5% tumour, 92% of simulated slides are flagged yellow or red; 5.8% of normal slides are flagged yellow (details in `engine/README.md`).

### Step 7 — Heatmap and Grad-CAM (TDD 2.3, 3.1 step 7) ✅ (#25; Grad-CAM deferred)
- `pipeline/heatmap.py`: build a patch-probability grid → upsample to image size → Green/Yellow/Red colormap → save a PNG overlay to local storage.
- Grad-CAM as a follow-up, run on the FP32 PyTorch/ONNX model, because gradients are not available from the INT8 model.
- Done: the heatmap interpolates patch probabilities, colours only tissue pixels, and outlines tiles with P ≥ 0.8 in bright cyan (TDD 6.2 focus cues). It takes ~0.45 s for a 12 MP image; `analyze_slide` takes ~0.9 s in total. Grad-CAM is deferred: it needs PyTorch (~2 GB) or a separate gradient model at runtime, for a sharper map than the patch map already gives.
- End-to-end check (step 2b goal) passed on `main`: three JPEG slides uploaded through the backend's `/ingest` went new → queued with the engine's score, flag and heatmap (normal 0.68 green; 5% and 100% tumour 0.88 / 0.95 red).

### Step 8 — Final entry point (interface contract) ✅
- Wire the real model (Steps 5–7) into `analyze_slide(image_path) -> dict` in `engine/pipeline/__init__.py` (set up in Step 2b):
  ```json
  { "score": 0.0, "risk_flag": "red|yellow|green", "heatmap_path": "...", "num_patches": 0, "inference_ms": 0 }
  ```
- Only `score` (0–1) is required. If `risk_flag` is missing, the backend derives it from its thresholds. See `backend/app/engine_adapter.py` for how results are validated.
- Add `onnxruntime` to `backend/requirements.txt` (coordinate with Member 2), because the engine runs in the backend's Python environment.
- Member 2's FastAPI `/ingest` calls this. Member 3 reads `risk_flag` and `heatmap_path`.
- Done: `analyze_slide` returns the full contract, including `risk_flag` (#20, #22, #25); `onnxruntime` is in `backend/requirements.txt` (#23); the model is committed (#24). The end-to-end `/ingest` check passed, and the packaged exe bundles the engine and model (`backend/backend.spec`, #27); the desktop app runs it (#28).

---

## Members 2 & 3 — summary
Members 2 and 3 plan their own detailed steps. Their dependencies on the engine are:
- **Backend (M2):** calls `analyze_slide()` after `/ingest`, stores `score`, `risk_flag` and `heatmap_path` in SQLite, and sorts the queue by `score` in descending order.
- **Frontend (M3):** shows `risk_flag` in the worklist and overlays `heatmap_path` with the opacity slider.

## Cross-team: magnification calibration (open, issue #35)
The model only works on photos at the magnification it was trained on: **about 0.42 µm per pixel**. It cannot tell the magnification from the photo, because µm/px depends on the whole setup: objective (10×/20×/40×), eyepiece, phone adapter, phone camera and zoom, and photo resolution.

**Evidence (PLISM, `engine/training/plism_eval.py`).** These are the same tissue spots imaged by 7 scanners and 6 smartphones on a microscope. The table shows the share of normal lymph-node patches the current model flags (P ≥ 0.5):

| Image scale | Scanners | Phones |
|---|---|---|
| as captured | 11–32% | 35–76% |
| resized to 0.6 (≈ 0.42 µm/px) | 0–10% | 0–6% |

At the right scale, phones are about as good as scanners. At the wrong scale, the triage is useless.

**Design**
1. **Calibrate each setup once** (microscope + phone + adapter). The technician photographs a stage micrometer (a slide with a printed scale, ~$10–20), clicks two marks a known distance apart, and the app stores µm/px for that setup and objective.
2. **Pick the objective** at every capture or upload. µm/px scales with objective power, so one calibration covers all objectives: `um_per_px(obj) = um_per_px(calibrated) × obj_calibrated / obj`.
3. **The engine resizes** each photo by `um_per_px / 0.42` before tiling.
4. **Later:** the engine estimates µm/px from nucleus size and warns when it disagrees with the selected setup (e.g. the wrong objective was picked). It is not accurate enough (±20–30%) to replace calibration.

**Who does what**
- **Engine (M1):** ✅ `analyze_slide(image_path, um_per_px=None)` resizes to `MODEL_UM_PER_PX = 0.42` before tiling (`engine/pipeline/scale.py`) and returns `um_per_px_used` and `scale_warning`. `None` keeps today's behaviour and sets `scale_warning`. Values outside 0.05–2.0 µm/px raise `ValueError`, since they are almost certainly a calibration or objective mistake. The heatmap stays the size of the original photo. Still to do: the nucleus-size mismatch warning (it will reuse `scale_warning`).
- **Backend (M2):** stores setup profiles (name, calibrated µm/px, objective calibrated at); `/ingest` and `/capture/snapshot` take `setup_id` + `objective`, compute µm/px, pass it to the engine and keep it on the slide record.
- **Frontend (M3):** a calibration screen (micrometer photo, click two marks, enter the distance); setup and objective pickers on upload and capture; a clear warning when no calibrated setup exists or the engine reports a scale mismatch.

**Done when** the same slide photographed at 10× and at 40× gets similar scores and heatmaps after calibration, and normal lymph-node false alarms stay under ~10% on phone captures.

## Open questions
- The TDD formula in 3.1 step 5 is garbled (`(Ppatch)w1`). This plan assumes it means `max(P_patch)`. Step 6 proposes w1 = 0, w2 = 1, k = 3 in log-odds space. Team to confirm.
- Red/Yellow/Green thresholds for `S_slide`. Step 6 proposes red ≥ 0.81 and yellow ≥ 0.70 (re-tuned for the distilled model, #38), returned by the engine as `risk_flag`, so the backend defaults (0.70 / 0.40) no longer apply. Team (Member 3) to confirm.
- ~~Frontend: the TDD says Electron + React, but `frontend/` is Next.js.~~ Resolved: the dashboard is Vite + React (#26) with an Electron desktop shell (#28).
- Repo layout: the TDD (7.2) uses `apps/`, `services/` and `engine/`, but the repo currently has `frontend/`, `backend/` and `engine/`. Keep the current layout unless the team decides otherwise.
- ~~Which training dataset to use, and whether its license allows redistribution of the weights.~~ Resolved: PCam (CC0), so the committed weights can be redistributed (step 3).
