# Front-end (React) - Team Member 3

Pathologist dashboard for the triage system: priority worklist, heatmap viewer and review actions,
in **Mongolian (default) and English**. TDD sections: 2.2 (front-end), 6.1, 6.2, 7.1, 8.1.

React 19 + TypeScript + Vite + Tailwind CSS v4. Server data goes through TanStack Query (polled, paused while
the tab is hidden). Dialogs and menus use Radix UI, and the slide viewer uses Leaflet. Fonts are bundled, so it
runs fully offline. Electron packaging (TDD 2.2) is the next step.

## Run

```bash
# 1. Backend (see backend/README.md): http://127.0.0.1:8000
cd backend && source .venv/bin/activate && python run_server.py

# 2. Dashboard (new terminal), then open http://localhost:5173
cd frontend
npm install
npm run dev
```

In development the dashboard calls `/api/...` and Vite forwards it to the backend without the prefix
(`VITE_BACKEND` changes the target). A packaged build talks to the backend directly. Set
`VITE_API_BASE=http://127.0.0.1:8000` at build time; the backend's CORS settings already allow Electron and port 5173.

## What it does

| Screen | Backend | TDD |
| --- | --- | --- |
| Worklist: AI risk flag (red / yellow / green), score 0–100, Routine/Urgent, "Sort by AI risk score" toggle (off = urgent first, then oldest) | `GET /queue?sort=risk` | 6.1 |
| Processing / failed strip, "Under review" and "Archived" tabs | `GET /slides` | 3.2 |
| New slide: upload a photo, or capture from the phone on the microscope (`uvc:0` or an `rtsp://` / `http://` stream) | `POST /ingest`, `/capture/*` | 2.1, 3.1 |
| Slide viewer: zoomable photo with the engine heatmap, 0–100% opacity, hotspot legend | `GET /slides/{id}/image`, `/heatmap` | 6.2 |
| Review: Start review, then Confirm malignancy / Mark benign / Request formal biopsy (each asks to confirm), Re-assign priority, Retry | `POST /slides/{id}/open`, `/action`, `/retry` | 6.2, 3.2 |
| Pipeline progress and audit history | `GET /slides/{id}/events` | 3.2 |
| Banner on every page: "prioritisation assistant, not a diagnostic engine" | | 8.1 |

Patient IDs are sent once and stored only as the backend's salted hash; the dashboard shows that code.
Blurry-photo rejections (`TRIAGE_SHARPNESS`) are explained in the viewer's language.

## Languages

- Text lives in `src/i18n/locales/<lang>/<namespace>.json`, never in components. To add a string, add the key
  to **both** `en` and `mn`. `t()` keys are type-checked against English. `npm test` fails if Mongolian misses a
  key, an `{{variable}}` or a `<tag>`, and `npm run test:e2e` fails if English text shows on a Mongolian page.
- Relative times and dates come from our own translations (`common:time.*`), because Chrome and Electron ship no
  Mongolian date data.
- Medical terms follow [`src/i18n/GLOSSARY.md`](src/i18n/GLOSSARY.md), which a Mongolian pathologist still needs to review.

## Checks

```bash
npm run lint           # oxlint
npm test               # unit + component tests (Vitest), incl. translation completeness
npm run build          # type-check + production bundle
npm run test:e2e       # browser tests in the installed Google Chrome, mocked API (~10 s)
npm run test:e2e:full  # + the real backend and ONNX engine (needs backend/.venv)
```

The mocked browser tests (`e2e/`) use an in-memory copy of the backend API, including its state machine.
After a failure, `npx playwright show-trace test-results/<test>/trace.zip` replays it step by step.

## Layout

```
src/app/        shell: providers, header, engine status, language switch, safety banner, error boundary
src/features/   worklist (list, sorting), upload (photo + camera), slide (page, score, review, history),
                viewer (Leaflet photo + heatmap), triage (risk flags, badges, priority levels)
src/shared/     api (client, types, TanStack Query hooks), lib (formatting, hooks), ui (primitives)
src/i18n/       i18next setup, locales/{mn,en}/*.json, GLOSSARY.md
e2e/            Playwright tests, mocked backend, fixtures
```
