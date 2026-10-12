# Backend (FastAPI) - Team Member 2

Local, offline-first API: image ingestion, SQLite slide records, triage-queue state machine and phone-capture transport.
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
| POST | `/ingest` | multipart `file`, `patient_id`, `indication` (Routine/Urgent) -> 202 `{id,state}` |
| GET | `/queue?sort=risk\|time` | worklist (state=queued), descending S_slide (manual priority wins) |
| GET | `/slides`, `/slides/{id}`, `/slides/{id}/events` | records / audit log |
| GET | `/slides/{id}/image`, `/slides/{id}/heatmap` | files |
| POST | `/slides/{id}/open` | queued -> under_review |
| POST | `/slides/{id}/action` | `confirm_malignancy` / `mark_benign` / `request_biopsy` (archive) or `reassign_priority` + `priority` 0-1 |
| POST | `/slides/{id}/retry` | failed -> re-run pipeline |
| POST | `/capture/start` `{source}` | `uvc:0` or `rtsp://...` |
| POST | `/capture/snapshot` | grab a frame -> same ingest pipeline |
| POST | `/capture/stop`, GET `/capture/status` | |

## State machine (TDD 3.2)
`new -> image_processing -> ai_running -> scored -> queued -> under_review -> archived` (`failed` on error; `retry` goes back to `new`).
Slides interrupted by a crash/power cut are marked `failed` on the next start.

## Engine contract (Member 1)
Expose `analyze_slide(image_path: str) -> dict` with `score` (0-1, required) and optional `risk_flag`
(`red|yellow|green`), `heatmap_path` (PNG), `num_patches`, `inference_ms`. Default entry point is
`engine.pipeline:analyze_slide` (override with `TRIAGE_ENGINE`). If it cannot be imported a stub scorer is used (logged as a warning).

## Configuration (env vars)
`TRIAGE_DATA_DIR`, `TRIAGE_HASH_SALT`, `TRIAGE_ENGINE`, `TRIAGE_RED`, `TRIAGE_YELLOW`, `TRIAGE_MAX_INFERENCE`, `TRIAGE_MAX_UPLOAD_MB`, `TRIAGE_HOST`, `TRIAGE_PORT`.

## Package (single offline executable)
```bash
pip install pyinstaller && pyinstaller backend.spec   # dist/triage-backend
```
