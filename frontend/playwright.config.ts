import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { defineConfig, devices } from '@playwright/test'

/**
 * Browser tests in the installed Google Chrome (the browser clinics use; no browser download needed).
 *
 * - `npm run test:e2e`: the dashboard against a mocked API (fast, deterministic, no backend needed).
 * - `npm run test:e2e:full`: also starts the real backend (with the ONNX engine) on a throwaway data
 *   folder and runs upload → AI score → review → archive. Needs the backend's Python environment
 *   (backend/.venv, see backend/README.md); set E2E_PYTHON to use another interpreter.
 */
const FULL = !!process.env.E2E_FULL
/** `npm run test:desktop`: launches the Electron app itself (e2e/desktop.spec.ts); no web server needed. */
const DESKTOP = !!process.env.E2E_DESKTOP
const UI_PORT = 5199
const API_PORT = 8012
// Windows keeps the virtualenv interpreter at .venv\Scripts\python.exe (same rule as electron/backend.cts).
const venvPython =
  process.platform === 'win32' ? join('.venv', 'Scripts', 'python.exe') : '.venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  testIgnore: [...(FULL ? [] : ['**/full-stack.spec.ts']), ...(DESKTOP ? [] : ['**/desktop.spec.ts'])],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${UI_PORT}`,
    channel: 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chrome', use: { ...devices['Desktop Chrome'], channel: 'chrome' } }],
  webServer: DESKTOP
    ? []
    : [
    {
      command: `npx vite --port ${UI_PORT} --strictPort`,
      url: `http://localhost:${UI_PORT}`,
      reuseExistingServer: !process.env.CI,
      env: { VITE_BACKEND: `http://127.0.0.1:${API_PORT}` },
    },
    ...(FULL
      ? [
          {
            command: `${process.env.E2E_PYTHON ?? venvPython} run_server.py`,
            cwd: '../backend',
            url: `http://127.0.0.1:${API_PORT}/health`,
            reuseExistingServer: false,
            timeout: 60_000,
            // Fresh database and images every run.
            env: { TRIAGE_PORT: String(API_PORT), TRIAGE_DATA_DIR: mkdtempSync(join(tmpdir(), 'triage-e2e-')) },
          },
        ]
      : []),
  ],
})
