# Desktop UI (Electron + React + Vite + Tailwind)

Owner: Member 3 (Front-End UI/UX & Packaging). See [../docs/PLAN.md](../docs/PLAN.md) and TDD sections 2.2, 6.1 and 6.2.

Built with [electron-vite](https://electron-vite.org). Talks to the FastAPI backend at `http://127.0.0.1:8000` (start it from `backend/`).

## Layout
- `src/main/`: Electron main process (window, app lifecycle)
- `src/preload/`: bridge between the main process and the page
- `src/renderer/`: the React app (Tailwind CSS v4 via `@tailwindcss/vite`)
- `electron-builder.yml`: installer settings (`.exe` via NSIS, `.AppImage` / `.deb`)

## Commands
```bash
npm install
npm run dev          # Electron window with hot reload (renderer dev server on :5173)
npm run lint
npm run typecheck
npm run build:win    # Windows installer in dist/
npm run build:linux  # AppImage + deb
```

## Notes
- The backend URL is `API_URL` in `src/renderer/src/api.ts` (override with `VITE_API_URL`). The page's Content-Security-Policy in `src/renderer/index.html` only allows requests and images from `127.0.0.1:8000` / `localhost:8000`, so update it if the URL changes.
- The backend's CORS settings already allow this app: the dev server (`http://localhost:5173`) and the packaged app (`file://`, origin `null`).
- No auto-update or telemetry is configured: the app is offline-first (TDD 7.1).
- npm 12 blocks dependency install scripts unless they are listed in `allowScripts` in `package.json`. Electron needs its script to download its binary; approve new ones with `npm install-scripts approve <package>`.
