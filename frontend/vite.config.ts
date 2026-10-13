/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The team backend (backend/run_server.py) listens on 127.0.0.1:8000 by default.
const backend = process.env.VITE_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The dashboard calls /api/...; the backend serves the same paths without the prefix. Keeping the
    // prefix in the browser stops page routes such as /slides/3 from colliding with API routes.
    proxy: { '/api': { target: backend, rewrite: (path) => path.replace(/^\/api/, '') } },
  },
  build: {
    rollupOptions: {
      output: {
        // Long-lived vendor chunks: app updates don't make clinics re-download libraries.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          i18n: ['i18next', 'react-i18next'],
          leaflet: ['leaflet', 'react-leaflet'],
        },
      },
    },
  },
  test: {
    // Unit and component tests only; e2e/ is Playwright's (npm run test:e2e).
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
