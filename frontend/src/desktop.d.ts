/** Set by the Electron preload script (electron/preload.cts); absent in a normal browser. */
interface Window {
  triageDesktop?: { apiBase?: string }
}
