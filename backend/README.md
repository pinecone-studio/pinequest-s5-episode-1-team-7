# Backend (FastAPI) - Team Member 2

Local, offline-first API: image ingestion, SQLite slide records, triage-queue state machine and magnification calibration.
TDD sections: 2.1, 2.2 (backend), 3.1 steps 1/2/6, 3.2.

## Run
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_server.py          # http://127.0.0.1:8000/docs
pytest                        # all tests
```
Data (DB, images, heatmaps) lives in `~/.pathology-triage` (override: `TRIAGE_DATA_DIR`).

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | multipart `file`, `patient_id`, `indication` (Routine/Urgent), `setup_id?`, `objective?` (`10x`/`20x`/`40x`), `organ?` (default `lymph_node`) -> 202 `{id,state}` |
| GET | `/queue?sort=risk\|time&organ?` | worklist (state=queued), descending S_slide (manual priority wins); `organ` filters (slides without organ count as `lymph_node`) |
| GET | `/slides`, `/slides/{id}`, `/slides/{id}/events` | records / audit log (`Slide` carries `setup_id`, `objective`, `um_per_px`, `scale_warning`, `model_name`, `model_sha256`, `organ`) |
| GET | `/model?organ?` | organ model card + live file + ONNX provider (About the AI; default organ when omitted) |
| GET | `/organs` | organ keys with a model file present, default first (never empties) |
| GET | `/slides/{id}/image`, `/slides/{id}/heatmap` | files |
| POST | `/slides/{id}/open` | queued -> under_review |
| POST | `/slides/{id}/action` | `confirm_malignancy` / `mark_benign` / `request_biopsy` (archive) or `reassign_priority` + `priority` 0-1 |
| POST | `/slides/{id}/retry` | failed -> re-run pipeline |
| GET | `/setups` | calibrated microscope + phone setups (issue #35) |
| POST | `/setups` | `{name, um_per_px, calibration_objective, phone_resolution?}` -> 201 |
| GET | `/setups/{id}` | one setup |
| DELETE | `/setups/{id}` | delete an unused setup (409 while slides use it) |

## State machine (TDD 3.2)
`new -> image_processing -> ai_running -> scored -> queued -> under_review -> archived` (`failed` on error; `retry` goes back to `new`).
Slides interrupted by a crash/power cut are marked `failed` on the next start.

## Engine contract (Member 1)
Expose `analyze_slide(image_path, um_per_px=None, organ=None) -> dict` with `score` (0-1, required) and optional `risk_flag`
(`red|yellow|green`), `heatmap_path` (PNG), `num_patches`, `inference_ms`, `um_per_px_used`, `scale_warning`, `organ`.
`organ` picks the organ's model (`available_organs()`, default `lymph_node`, no fallback); unknown organs raise ValueError.
`model_info(organ=None)` returns the organ card + live status. Default entry point is
`engine.pipeline:analyze_slide` (override with `TRIAGE_ENGINE`). If it cannot be imported a stub scorer is used (logged as a warning).

## Configuration (env vars)
`TRIAGE_DATA_DIR`, `TRIAGE_HASH_SALT`, `TRIAGE_ENGINE`, `TRIAGE_RED`, `TRIAGE_YELLOW`, `TRIAGE_MAX_INFERENCE`, `TRIAGE_MAX_UPLOAD_MB`, `TRIAGE_HOST`, `TRIAGE_PORT`, `TRIAGE_SHARPNESS`.

`TRIAGE_SHARPNESS` is the Laplacian-variance blur gate (TDD 8.1): captures scoring
below it are rejected with 422 so the technician retakes them in focus. `<= 0`
(default) disables the check. Scores are measured at a fixed working size so one
value works across capture resolutions, but absolute scores still depend on the
setup (microscope + phone + adapter + objective) — sharp real tiles range from
~10 to ~600 (issue #40), so there is no good universal default. Calibrate per
setup: photograph a few sharp and a few deliberately defocused captures, then run
(from `backend/`):

```bash
python -m app.quality sharp_dir/ blurry_dir/ [--um-per-px 0.84]   # distributions + a suggestion
```

and set `TRIAGE_SHARPNESS` to the suggested value. Pass the setup's µm/px
when the folders hold one setup + objective: slides ingested with that
setup are then scored at the model's scale, so the same physical defocus
scores the same at any objective. The desktop app will pass a
validated default (overridable by clinic IT) once calibration data exists.

## Package (single offline executable)
```bash
pip install pyinstaller && pyinstaller backend.spec   # dist/triage-backend
```
