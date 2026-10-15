# Pathology Triage (pinequest-s5-episode-1-team-7)

Offline AI triage for pathology slides: a phone on a microscope takes the photo, a local AI model scores it,
and the most suspicious slides go to the top of the pathologist's worklist with a heatmap over the risky areas.
It runs entirely on one clinic PC, with no internet. It is a **prioritisation assistant, not a diagnosis**:
every slide must still be reviewed by a pathologist.

See [docs/TDD.md](docs/TDD.md) for the technical design and [docs/PLAN.md](docs/PLAN.md) for the plan.

## Quick start

### Option 1: install the desktop app (clinic PCs)

1. Get the installer for your system:
   - **Build it yourself:** see [Option 3](#option-3-build-the-installer-yourself). This is currently the only way.
   - **From GitHub (not available yet):** the **Desktop build** workflow is meant to publish installers as
     **Artifacts** of its runs (Actions tab → Desktop build → a run → `pathology-triage-Windows` / `-macOS` /
     `-Linux`). But GitHub Actions has never run in this repository (no workflow runs at all), so there are no
     downloads yet. An organisation admin needs to enable Actions first.
2. Install it:
   - **Windows:** run the `.exe`. If SmartScreen warns, click **More info → Run anyway**.
   - **macOS:** open the `.dmg` and drag **Pathology Triage** into Applications. The first time, **right-click the
     app → Open → Open**, because it is not signed by an Apple developer account.
   - **Linux:** make the `.AppImage` executable (`chmod +x`) and run it.
3. Open **Pathology Triage**. The first start takes up to a minute while the local AI service starts.
4. In the upload panel, click **Тохиргоо калибровк хийх / Calibrate a setup** and calibrate your microscope + phone once with a stage micrometer.
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
   - **Windows:** double-click `start.bat`, or run `.\start.bat` in PowerShell (`start.bat` in Command Prompt)
3. The dashboard opens at **http://localhost:5173**. The backend's API docs are at http://127.0.0.1:8000/docs.
4. To stop, press **Ctrl+C** in the terminal (on Windows, close both windows).

Data (the database, photos and heatmaps) is kept in `~/.pathology-triage`. Delete that folder to start fresh.

#### The desktop app from source (no browser, no installer)
To test the real desktop window (Electron) without building an installer, with **Node.js 22.12+**:
1. Run the start script above once and close it. It creates `backend/.venv` and installs the dashboard packages,
   which the desktop app uses.
2. In a terminal:
   ```bash
   cd frontend
   npm run desktop:dev
   ```
   The desktop window opens. It starts its own backend from `backend/.venv` and stops it when you close the window.
   The first run downloads Electron (~150 MB), so it needs internet once.

`npm run test:desktop` runs the same app automatically through a full upload → review flow and closes it again.

### Option 3: build the installer yourself

Installers can only be built on the system they are for (a `.dmg` on macOS, an `.exe` on Windows).
You need Python 3.11+ and **Node.js 22.12+**.

macOS / Linux:
```bash
# 1. Package the backend and AI engine into one executable -> backend/dist/triage-backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm backend.spec

# 2. Build the desktop installer -> frontend/release/
cd ../frontend
npm ci
node scripts/smoke-backend.mjs ../backend/dist/triage-backend   # checks it runs the real AI model
npm run desktop:build
```

Windows (PowerShell):
```powershell
# 1. Package the backend and AI engine into one executable -> backend\dist\triage-backend.exe
cd backend
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.venv\Scripts\pyinstaller --noconfirm backend.spec

# 2. Build the installer -> frontend\release\Pathology Triage Setup <version>.exe
cd ..\frontend
npm ci
node scripts/smoke-backend.mjs ..\backend\dist\triage-backend.exe   # checks it runs the real AI model
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
- **`start.bat` stops with "... was unexpected at this time."**: fixed on `main`; pull the latest code.
- **The dashboard shows a blank page after a pull** (Vite: "Failed to resolve import"): the start scripts now
  reinstall the dashboard packages when they change. If you start Vite yourself, run `npm ci` in `frontend` first.
- **`npm run desktop:dev` fails with "Electron failed to install correctly"**: your Node.js is older than 22.12,
  or the first-run Electron download failed. Install Node.js 22+, delete `frontend/node_modules/electron`, and run
  `npm ci` in `frontend` again (with internet).
- **The desktop app fails with "electron.exe: bad option: --remote-debugging-port"** (or the window never opens):
  the `ELECTRON_RUN_AS_NODE` environment variable is set, which some editor and AI-assistant shells do. It makes
  Electron run as plain Node. Start it from a normal terminal, or clear the variable first (PowerShell:
  `Remove-Item Env:ELECTRON_RUN_AS_NODE`).

## License

[MIT](LICENSE) (TDD 1.2). Third-party datasets and model weights keep their own licenses; see `engine/README.md` and `frontend/e2e/fixtures/README.md`.
