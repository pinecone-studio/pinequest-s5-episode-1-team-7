# Pathology Triage (pinequest-s5-episode-1-team-7)

Offline AI triage for pathology slides: a phone on a microscope takes the photo, a local AI model scores it,
and the most suspicious slides go to the top of the pathologist's worklist with a heatmap over the risky areas.
It runs entirely on one clinic PC, with no internet. It is a **prioritisation assistant, not a diagnosis**:
every slide must still be reviewed by a pathologist.

See [docs/TDD.md](docs/TDD.md) for the technical design and [docs/PLAN.md](docs/PLAN.md) for the plan.

## Quick start

### Option 1: install the desktop app (clinic PCs)

1. Get the installer for your system:
   - **From GitHub:** open the repository's **Actions** tab → **Desktop build** → the latest successful run →
     **Artifacts**, and download `pathology-triage-Windows` (`.exe`), `-macOS` (`.dmg`) or `-Linux` (`.AppImage`).
     Anyone with write access can start a new build with **Run workflow**.
   - **Or build it yourself:** see [Option 3](#option-3-build-the-installer-yourself).
2. Install it:
   - **Windows:** run the `.exe`. If SmartScreen warns, click **More info → Run anyway**.
   - **macOS:** open the `.dmg` and drag **Pathology Triage** into Applications. The first time, **right-click the
     app → Open → Open**, because it is not signed by an Apple developer account.
   - **Linux:** make the `.AppImage` executable (`chmod +x`) and run it.
3. Open **Pathology Triage**. The first start takes up to a minute while the local AI service starts.
4. Click **Калибровк / Calibration** and calibrate your microscope + phone once with a stage micrometer.
   Without it, scores are unreliable (the app warns about this).
5. Take the slide photo with the phone on the microscope and upload it. It appears in the worklist with its risk flag.

### Option 2: run from source (developers)

You need **[Git](https://git-scm.com/)**, **[Python 3.11+](https://www.python.org/downloads/)** and
**[Node.js](https://nodejs.org/) 20+** (22.12+ for the desktop app).

1. Get the code:
   ```bash
   git clone https://github.com/pinecone-studio/pinequest-s5-episode-1-team-7.git
   cd pinequest-s5-episode-1-team-7
   ```
2. Start everything with one command. The first run installs the dependencies, which takes a few minutes.
   - **macOS:** double-click `start.command` in Finder, or run `./start.sh`
   - **Linux:** `./start.sh`
   - **Windows:** double-click `start.bat`
3. The dashboard opens at **http://localhost:5173**. The backend's API docs are at http://127.0.0.1:8000/docs.
4. To stop, press **Ctrl+C** in the terminal (on Windows, close both windows).

Data (the database, photos and heatmaps) is kept in `~/.pathology-triage`. Delete that folder to start fresh.

To run the desktop app from source instead of the browser, with Node.js 22.12+:
```bash
cd frontend && npm install && npm run desktop:dev
```

### Option 3: build the installer yourself

Installers can only be built on the system they are for (a `.dmg` on macOS, an `.exe` on Windows).
You need Python 3.11+ and **Node.js 22.12+**.

```bash
# 1. Package the backend and AI engine into one executable -> backend/dist/triage-backend
cd backend
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm backend.spec

# 2. Build the desktop installer -> frontend/release/
cd ../frontend
npm ci
node scripts/smoke-backend.mjs ../backend/dist/triage-backend   # checks it runs the real AI model
npm run desktop:build
```

## Project layout

| Folder | What it is | Details |
|---|---|---|
| `engine/` | AI engine: tiling, background masking, the ONNX model, scoring and heatmaps | [engine/README.md](engine/README.md) |
| `backend/` | Local FastAPI service: photo ingest, SQLite worklist, calibration setups | [backend/README.md](backend/README.md) |
| `frontend/` | Dashboard (React, Mongolian and English) and the Electron desktop app | [frontend/README.md](frontend/README.md) |
| `docs/` | Technical design, plan and test plans | |

## Troubleshooting

- **"Something is already running on port 8000"**: another copy of the backend is running. Close it, or stop the
  process that uses port 8000.
- **Every slide fails with "AI model not found"**: `engine/model/model_fp32.onnx` is missing. Pull the latest
  `main`, or see [engine/README.md](engine/README.md) to train and export it.
- **`npm run desktop:dev` fails with "Electron failed to install correctly"**: your Node.js is older than 22.12.
  Install Node.js 22, delete `frontend/node_modules`, and run `npm install` again.

## License

[MIT](LICENSE) (TDD 1.2). Third-party datasets and model weights keep their own licenses; see `engine/README.md` and `frontend/e2e/fixtures/README.md`.
