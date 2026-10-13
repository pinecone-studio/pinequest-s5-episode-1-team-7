import { app, BrowserWindow, dialog, session, shell } from 'electron'
import path from 'node:path'

import { type RunningBackend, startBackend } from './backend.cjs'
import { failedScreen, startingScreen } from './screens.cjs'

/**
 * Desktop shell (TDD 2.2): starts the local FastAPI backend, then shows the dashboard. Everything stays
 * on this computer: the window may only load the app's own files and the backend on 127.0.0.1.
 */

/** Development: Vite's dev server (set by scripts/desktop-dev.mjs). Packaged: the built dist-desktop/. */
const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL
const FRONTEND_DIR = path.resolve(__dirname, '..')

let backend: RunningBackend | undefined
let quitting = false

// A second copy would start a second backend on the same database: focus the first one instead.
const firstInstance = app.requestSingleInstanceLock()
if (!firstInstance) app.quit()

app.on('second-instance', () => {
  const win = BrowserWindow.getAllWindows()[0]
  if (win) {
    if (win.isMinimized()) win.restore()
    win.focus()
  }
})

/** Blocks every request that isn't the app itself or the local backend (TDD 7.1: zero telemetry). */
function lockDownNetwork() {
  const allowed = (url: string) => {
    if (url.startsWith('file:') || url.startsWith('data:') || url.startsWith('blob:') || url.startsWith('devtools:')) return true
    const { hostname } = new URL(url)
    return hostname === '127.0.0.1' || (DEV_SERVER_URL != null && hostname === 'localhost')
  }
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => callback({ cancel: !allowed(details.url) }))
  // The dashboard needs no camera, microphone, location or notifications; capture runs in the backend.
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false))
}

function createWindow(apiBase?: string) {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#020617',
    title: 'Pathology Triage',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      additionalArguments: apiBase ? [`--triage-api=${apiBase}`] : [],
    },
  })
  win.once('ready-to-show', () => win.show())
  // No pop-ups; never navigate away from the dashboard.
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  win.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file:') && !(DEV_SERVER_URL && url.startsWith(DEV_SERVER_URL))) event.preventDefault()
  })
  return win
}

function loadDashboard(win: BrowserWindow) {
  if (DEV_SERVER_URL) return win.loadURL(DEV_SERVER_URL)
  return win.loadFile(path.join(FRONTEND_DIR, 'dist-desktop', 'index.html'))
}

async function start() {
  lockDownNetwork()
  const logFile = path.join(app.getPath('logs'), 'backend.log')
  const splash = createWindow()
  await splash.loadURL(startingScreen())

  try {
    backend = await startBackend({
      packaged: app.isPackaged,
      resourcesPath: app.isPackaged ? process.resourcesPath : FRONTEND_DIR,
      // TRIAGE_DATA_DIR (the backend's own setting) lets clinic IT put patient data on a chosen disk.
      dataDir: process.env.TRIAGE_DATA_DIR ?? path.join(app.getPath('userData'), 'data'),
      logFile,
    })
  } catch (err) {
    await splash.loadURL(failedScreen((err as Error).message, logFile))
    return
  }

  backend.process.once('exit', async () => {
    if (quitting) return
    const { response } = await dialog.showMessageBox({
      type: 'error',
      message: 'Эрэмбэлэх систем зогслоо · The triage engine stopped',
      detail: `Програмыг дахин эхлүүлнэ үү. · Please restart the app.\n\n${logFile}`,
      buttons: ['Дахин эхлүүлэх · Restart', 'Бүртгэл харах · Show log', 'Хаах · Quit'],
      defaultId: 0,
    })
    if (response === 1) shell.showItemInFolder(logFile)
    if (response === 0) {
      app.relaunch()
    }
    app.quit()
  })

  const win = createWindow(backend.url)
  await loadDashboard(win)
  splash.destroy()
}

if (firstInstance) app.whenReady().then(start)

app.on('window-all-closed', () => app.quit())

app.on('before-quit', (event) => {
  if (quitting || !backend) return
  // Stop the backend first so no orphaned server keeps the port or the database open.
  quitting = true
  event.preventDefault()
  void backend.stop().finally(() => app.quit())
})
