import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { _electron as electron, type ElectronApplication, expect, type Page, test } from '@playwright/test'

import { SLIDE_PHOTO } from './helpers.ts'

/**
 * The Electron app end to end (npm run test:desktop): it starts the backend, loads the built dashboard
 * from disk under its Content-Security-Policy, and stops the backend on quit. By default it runs the
 * development build with backend/.venv; set E2E_DESKTOP_APP to a packaged app's executable (e.g.
 * "release/mac-arm64/Pathology Triage.app/Contents/MacOS/Pathology Triage") to test the installer contents.
 */
const FRONTEND = fileURLToPath(new URL('..', import.meta.url))
const PACKAGED = process.env.E2E_DESKTOP_APP

async function dashboardWindow(app: ElectronApplication): Promise<Page> {
  // The first window is the start-up screen; the dashboard opens once the backend is healthy.
  await expect.poll(() => app.windows().some((w) => w.url().startsWith('file:')), { timeout: 90_000 }).toBe(true)
  return app.windows().find((w) => w.url().startsWith('file:'))!
}

test('starts the backend, runs the full review flow offline, and stops the backend on quit', async () => {
  test.setTimeout(180_000)
  // A fresh profile (language choice, window state) and data folder every run.
  const profile = `--user-data-dir=${mkdtempSync(join(tmpdir(), 'triage-profile-'))}`
  const app = await electron.launch({
    ...(PACKAGED ? { executablePath: PACKAGED, args: [profile] } : { args: ['.', profile], cwd: FRONTEND }),
    env: { ...process.env, TRIAGE_DATA_DIR: mkdtempSync(join(tmpdir(), 'triage-desktop-')) },
  })
  const win = await dashboardWindow(app)
  const problems: string[] = []
  win.on('console', (msg) => msg.type() === 'error' && problems.push(msg.text()))

  // Mongolian by default, backend reachable through the address Electron passed in.
  await expect(win.getByRole('heading', { name: 'Эрэмбэлсэн ажлын жагсаалт' })).toBeVisible()
  await expect(win.getByText('Эрэмбэлэх систем ажиллаж байна')).toBeVisible()
  const apiBase = await win.evaluate(() => window.triageDesktop?.apiBase)
  expect(apiBase).toMatch(/^http:\/\/127\.0\.0\.1:\d+$/)

  await win.getByRole('radio', { name: 'EN' }).click()
  await win.getByRole('radio', { name: 'Urgent' }).click()
  await win.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  await win.getByRole('button', { name: 'Submit for AI triage' }).click()

  const row = win.getByRole('list', { name: 'Worklist' }).getByRole('link', { name: /Slide #1/ })
  await expect(row).toBeVisible({ timeout: 60_000 })
  await row.click()
  await expect(win).toHaveURL(/#\/slides\/1$/) // hash routing from file://
  await expect(win.locator('.leaflet-container img')).toHaveCount(2) // photo + heatmap pass the CSP
  await win.getByRole('button', { name: 'Start review' }).click()
  await win.getByRole('button', { name: 'Mark benign' }).click()
  await win.getByRole('dialog').getByRole('button', { name: 'Mark benign' }).click()
  await expect(win.getByText('No slides waiting. Add a slide photo to begin.')).toBeVisible()

  // Outside requests are blocked (TDD 7.1): nothing leaves the computer.
  const outside = await win.evaluate(() => fetch('https://example.com').then(() => 'reached', () => 'blocked'))
  expect(outside).toBe('blocked')
  expect(problems.filter((p) => !p.includes('example.com'))).toEqual([])

  await app.close()
  const afterQuit = await fetch(`${apiBase}/health`).then(() => 'running', () => 'stopped')
  expect(afterQuit).toBe('stopped')
})
