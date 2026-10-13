// npm run desktop:dev: Vite dev server (hot reload) + Electron, with the backend from backend/.venv.
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import electron from 'electron'
import { createServer } from 'vite'

const root = fileURLToPath(new URL('..', import.meta.url))
const server = await createServer({ root, server: { port: 5173, strictPort: false } })
await server.listen()
const url = server.resolvedUrls.local[0]

const app = spawn(String(electron), ['.'], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, VITE_DEV_SERVER_URL: url },
})
app.on('exit', async (code) => {
  await server.close()
  process.exit(code ?? 0)
})
