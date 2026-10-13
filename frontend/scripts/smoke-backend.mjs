// Checks that a packaged backend runs the real AI engine, not the stub scorer.
// Usage: node scripts/smoke-backend.mjs ../backend/dist/triage-backend[.exe]
// The stub (backend/app/engine_adapter.py) always reports num_patches = 1, so a real result has more.
import { spawn } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const exe = resolve(process.argv[2] ?? '')
const photo = fileURLToPath(new URL('../e2e/fixtures/slide.jpg', import.meta.url))
const port = 8765
const api = `http://127.0.0.1:${port}`
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const child = spawn(exe, [], {
  env: { ...process.env, TRIAGE_PORT: String(port), TRIAGE_DATA_DIR: mkdtempSync(join(tmpdir(), 'triage-smoke-')) },
  stdio: 'inherit',
  detached: process.platform !== 'win32',
})
const stop = () => {
  if (process.platform === 'win32') spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'])
  else process.kill(-child.pid, 'SIGTERM')
}

async function poll(fn, timeoutMs, what) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = await fn().catch(() => undefined)
    if (value !== undefined) return value
    await sleep(500)
  }
  throw new Error(`timed out waiting for ${what}`)
}

try {
  // A one-file PyInstaller build unpacks itself first, so allow a slow start.
  await poll(async () => ((await fetch(`${api}/health`)).ok ? true : undefined), 180_000, 'the backend to start')
  const form = new FormData()
  form.append('file', new Blob([readFileSync(photo)], { type: 'image/jpeg' }), 'slide.jpg')
  const { id } = await (await fetch(`${api}/ingest`, { method: 'POST', body: form })).json()
  const slide = await poll(
    async () => {
      const s = await (await fetch(`${api}/slides/${id}`)).json()
      return s.state === 'queued' || s.state === 'failed' ? s : undefined
    },
    120_000,
    'the slide to be scored',
  )
  console.log('Scored slide:', JSON.stringify(slide))
  if (slide.state !== 'queued') throw new Error(`slide ${slide.state}: ${slide.error}`)
  if (!(slide.num_patches > 1)) throw new Error('num_patches is 1: the backend is using the STUB scorer, not the AI engine')
  if (!slide.has_heatmap) throw new Error('no heatmap')
  console.log('OK: the packaged backend runs the AI engine.')
  stop()
} catch (err) {
  console.error(`FAILED: ${err.message}`)
  stop()
  process.exit(1)
}
