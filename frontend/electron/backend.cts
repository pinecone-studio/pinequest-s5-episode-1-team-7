import { type ChildProcess, spawn } from 'node:child_process'
import { createWriteStream, existsSync, mkdirSync } from 'node:fs'
import { createServer } from 'node:net'
import path from 'node:path'

/** How to start the backend: the PyInstaller executable when packaged, Python in development. */
export interface BackendCommand {
  command: string
  args: string[]
  cwd: string
}

export interface BackendOptions {
  /** True inside the packaged app (Electron's app.isPackaged). */
  packaged: boolean
  /** Electron's process.resourcesPath (packaged) or the frontend/ folder (development). */
  resourcesPath: string
  /** Where the backend keeps its database, images and heatmaps (TRIAGE_DATA_DIR). */
  dataDir: string
  logFile: string
  platform?: NodeJS.Platform
  env?: NodeJS.ProcessEnv
}

/**
 * Packaged: <resources>/backend/triage-backend[.exe] (built by backend/backend.spec).
 * Development: backend/.venv's Python running run_server.py; TRIAGE_BACKEND_PYTHON overrides it.
 */
export function backendCommand({ packaged, resourcesPath, platform = process.platform, env = process.env }: BackendOptions): BackendCommand {
  if (packaged) {
    const exe = platform === 'win32' ? 'triage-backend.exe' : 'triage-backend'
    const dir = path.join(resourcesPath, 'backend')
    return { command: path.join(dir, exe), args: [], cwd: dir }
  }
  const backendDir = path.resolve(resourcesPath, '..', 'backend')
  const venvPython =
    platform === 'win32' ? path.join(backendDir, '.venv', 'Scripts', 'python.exe') : path.join(backendDir, '.venv', 'bin', 'python')
  return { command: env.TRIAGE_BACKEND_PYTHON ?? venvPython, args: ['run_server.py'], cwd: backendDir }
}

/** A TCP port that is free on 127.0.0.1 right now. */
export function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.unref()
    server.on('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      server.close(() => (typeof address === 'object' && address ? resolve(address.port) : reject(new Error('no port'))))
    })
  })
}

/** Polls GET {url}/health until it answers 200, the process exits, or `timeoutMs` passes. */
export async function waitForHealth(url: string, { timeoutMs, exited }: { timeoutMs: number; exited: () => boolean }) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (exited()) throw new Error('The triage backend stopped while starting.')
    try {
      const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(2000) })
      if (res.ok) return
    } catch {
      /* not listening yet */
    }
    await new Promise((r) => setTimeout(r, 300))
  }
  throw new Error(`The triage backend did not start within ${Math.round(timeoutMs / 1000)} s.`)
}

export interface RunningBackend {
  url: string
  process: ChildProcess
  stop: () => Promise<void>
}

/**
 * Starts the backend on a free localhost port and resolves once it is healthy. Output goes to `logFile`.
 * A one-file PyInstaller build unpacks itself on first start, which can take tens of seconds.
 */
export async function startBackend(options: BackendOptions, { timeoutMs = 120_000 } = {}): Promise<RunningBackend> {
  const { command, args, cwd } = backendCommand(options)
  if (!existsSync(command)) throw new Error(`Triage backend not found at ${command}`)
  mkdirSync(options.dataDir, { recursive: true })
  mkdirSync(path.dirname(options.logFile), { recursive: true })

  const port = await freePort()
  const log = createWriteStream(options.logFile, { flags: 'a' })
  log.write(`\n--- ${new Date().toISOString()} starting ${command} on port ${port}\n`)
  const child = spawn(command, args, {
    cwd,
    env: {
      ...(options.env ?? process.env),
      TRIAGE_HOST: '127.0.0.1',
      TRIAGE_PORT: String(port),
      TRIAGE_DATA_DIR: options.dataDir,
      // Blur gate (TDD 8.1, issue #40): off until a per-setup threshold is validated
      // with `python -m app.quality`. Clinic IT can enable it with a system-wide
      // TRIAGE_SHARPNESS, the way TRIAGE_DATA_DIR above is overridden.
      TRIAGE_SHARPNESS: options.env?.TRIAGE_SHARPNESS ?? process.env.TRIAGE_SHARPNESS ?? '0',
      PYTHONUNBUFFERED: '1',
    },
    // Own process group on macOS/Linux, so stop() also reaches the child a PyInstaller build spawns.
    detached: process.platform !== 'win32',
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  child.stdout?.pipe(log, { end: false })
  child.stderr?.pipe(log, { end: false })
  let exited = false
  child.once('exit', (code, signal) => {
    exited = true
    log.write(`--- backend exited (code ${code}, signal ${signal})\n`)
  })

  const url = `http://127.0.0.1:${port}`
  const stop = () => stopProcess(child)
  try {
    await waitForHealth(url, { timeoutMs, exited: () => exited })
  } catch (err) {
    await stop()
    throw err
  }
  return { url, process: child, stop }
}

/** Ends the backend and anything it started; resolves when it has exited. */
function stopProcess(child: ChildProcess): Promise<void> {
  if (child.exitCode != null || child.signalCode != null || child.pid == null) return Promise.resolve()
  return new Promise((resolve) => {
    const done = setTimeout(resolve, 5000) // never block quitting on a stuck process
    child.once('exit', () => {
      clearTimeout(done)
      resolve()
    })
    try {
      if (process.platform === 'win32') {
        // Kills the whole tree: the PyInstaller bootloader and the Python process it starts.
        spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true })
      } else {
        process.kill(-child.pid!, 'SIGTERM')
      }
    } catch {
      child.kill('SIGKILL')
    }
  })
}
