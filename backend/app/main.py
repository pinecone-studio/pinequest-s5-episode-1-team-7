import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, queue
from .routers import ingest, model, organs, setups, slides

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.ensure_dirs()
    db.init_db()
    with db.session() as conn:
        n = queue.recover_interrupted(conn)  # slides left mid-pipeline by a crash / power cut
    if n:
        log.warning("%d interrupted slide(s) marked failed; retry via POST /slides/{id}/retry", n)
    yield


app = FastAPI(title="Pathology Triage Backend", version="1.0.0", lifespan=lifespan)

# Electron renderer (file:// -> Origin "null") and the React dev servers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(slides.router)
app.include_router(setups.router)
app.include_router(model.router)
app.include_router(organs.router)


@app.get("/health")
def health():
    return {"status": "ok"}


def run() -> None:
    """Entry point for `python run_server.py` and PyInstaller. Binds to localhost only (offline-first)."""
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    run()
