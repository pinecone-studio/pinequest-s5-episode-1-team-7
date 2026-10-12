// FastAPI backend on the same PC. If you change it, also update connect-src/img-src in index.html.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
