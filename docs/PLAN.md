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

### Step 1 — Image tiling (TDD 3.1 step 3)
- `pipeline/tiling.py`: split a high-res image into 224×224 patches, keeping each patch's (row, col) position for the heatmap later.
- Handle edges (pad or drop partial tiles; decide and document).
- Tests: tile count and coordinates for known image sizes.

### Step 2 — Background masking (TDD 5.2, 3.1 step 3, 8.1)
- `pipeline/masking.py`:
  - Otsu threshold on grayscale → tissue mask.
  - RGB→HSV saturation filter to drop blank and white background.
  - Tissue fraction per patch; drop patches below a threshold (e.g. < 50% tissue).
- Optional CLAHE for uneven lighting (TDD 8.1).
- Tests: a blank image gives 0 patches; a synthetic "tissue" region is kept.

### Step 2b — End-to-end skeleton (no model yet)
Get the whole system running early, before the model exists.
- `analyze_slide(image_path)` in `engine/pipeline/__init__.py`, the entry point the backend loads (`engine.pipeline:analyze_slide`).
- Uses the real tiling and masking from Steps 1–2, with a **placeholder** per-patch score (e.g. stain saturation) and a simple patch heatmap PNG.
- Returns the contract dict (see Step 8). From then on the backend uses it instead of its built-in stub.
- Done when an image uploaded through the backend's `/ingest` gets a score and a heatmap from the engine.
- Steps 3–7 then replace the placeholder pieces one at a time, without changing the contract.

### Step 3 — Model setup and ONNX export (TDD 2.3, 4)
- Start from pretrained MobileNetV3-Small (fallback: ResNet-18) with a binary head (benign / malignant).
- Fine-tune on a public histopathology dataset (e.g. PCam or BreakHis); keep the training script in `engine/training/`.
- Export to `engine/model/model_fp32.onnx`. Record accuracy / AUC on a held-out set.
- Result (PCam, MobileNetV3-Small, 224 px, strong augmentation + EMA): test AUC 0.960, accuracy 86.0%, 0.29 s CPU per slide (FP32). The first 96 px run scored AUC 0.919. Details in `engine/README.md` and `engine/training/results/`.

### Step 4 — INT8 quantization (TDD 5.2)
- `onnxruntime.quantization.quantize_static` with a small calibration set → `model_int8.onnx`.
- Compare FP32 and INT8 size (target about 75% smaller), AUC drop, and CPU latency. Target: under 1.5 s per slide.

### Step 5 — Inference runner (TDD 3.1 step 4, 5.2)
- `pipeline/inference.py`: load the ONNX session with provider fallback (DirectML / OpenVINO → CPU).
- Dynamic batching (N = 8 or 16) → `P_malignant ∈ [0,1]` per patch.

### Step 6 — Slide-level score (TDD 3.1 step 5)
- `pipeline/scoring.py`: `S_slide = w1 · max(P_patch) + w2 · mean(top-k P_patch)`.
- Map S_slide to a Red / Yellow / Green risk flag (thresholds to agree with Member 3).
- Tests: known probability arrays → expected score and flag.

### Step 7 — Heatmap and Grad-CAM (TDD 2.3, 3.1 step 7)
- `pipeline/heatmap.py`: build a patch-probability grid → upsample to image size → Green/Yellow/Red colormap → save a PNG overlay to local storage.
- Grad-CAM as a follow-up, run on the FP32 PyTorch/ONNX model, because gradients are not available from the INT8 model.

### Step 8 — Final entry point (interface contract)
- Wire the real model (Steps 5–7) into `analyze_slide(image_path) -> dict` in `engine/pipeline/__init__.py` (set up in Step 2b):
  ```json
  { "score": 0.0, "risk_flag": "red|yellow|green", "heatmap_path": "...", "num_patches": 0, "inference_ms": 0 }
  ```
- Only `score` (0–1) is required. If `risk_flag` is missing, the backend derives it from its thresholds. See `backend/app/engine_adapter.py` for how results are validated.
- Add `onnxruntime` to `backend/requirements.txt` (coordinate with Member 2), because the engine runs in the backend's Python environment.
- Member 2's FastAPI `/ingest` calls this. Member 3 reads `risk_flag` and `heatmap_path`.

---

## Members 2 & 3 — summary
Members 2 and 3 plan their own detailed steps. Their dependencies on the engine are:
- **Backend (M2):** calls `analyze_slide()` after `/ingest`, stores `score`, `risk_flag` and `heatmap_path` in SQLite, and sorts the queue by `score` in descending order.
- **Frontend (M3):** shows `risk_flag` in the worklist and overlays `heatmap_path` with the opacity slider.

## Open questions
- The TDD formula in 3.1 step 5 is garbled (`(Ppatch)w1`). This plan assumes it means `max(P_patch)`. Confirm with the team, along with values for w1, w2 and k.
- Red/Yellow/Green thresholds for `S_slide`. The backend currently defaults to red ≥ 0.70 and yellow ≥ 0.40 (`TRIAGE_RED`, `TRIAGE_YELLOW`).
- Frontend: the TDD says Electron + React, but `frontend/` is Next.js. The backend's CORS settings allow Electron and port 5173 (Vite), but not port 3000 (Next.js dev).
- Repo layout: the TDD (7.2) uses `apps/`, `services/` and `engine/`, but the repo currently has `frontend/`, `backend/` and `engine/`. Keep the current layout unless the team decides otherwise.
- Which training dataset to use, and whether its license allows redistribution of the weights.
