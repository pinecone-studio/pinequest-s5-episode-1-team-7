import { contextBridge } from 'electron'

/** Passed by main.cts as --triage-api=<url>: the backend this window talks to. */
const apiArg = process.argv.find((arg) => arg.startsWith('--triage-api='))

// The only thing the dashboard gets from Electron: where the local backend is. No Node APIs.
contextBridge.exposeInMainWorld('triageDesktop', {
  apiBase: apiArg ? apiArg.slice('--triage-api='.length) : undefined,
})
