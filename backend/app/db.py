"""SQLite access layer (stdlib sqlite3 keeps the PyInstaller binary small).

Encryption at rest (SQLCipher, TDD 7.1) can be added later by changing only `connect()`.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS slides (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    local_hash        TEXT NOT NULL,
    indication        TEXT NOT NULL DEFAULT 'Routine',
    state             TEXT NOT NULL,
    risk_score        REAL,
    risk_flag         TEXT,
    priority_override REAL,
    image_path        TEXT NOT NULL,
    heatmap_path      TEXT,
    num_patches       INTEGER,
    inference_ms      REAL,
    decision          TEXT,
    error             TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_slides_state ON slides(state);
CREATE TABLE IF NOT EXISTS slide_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    slide_id   INTEGER NOT NULL REFERENCES slides(id),
    from_state TEXT,
    to_state   TEXT NOT NULL,
    note       TEXT,
    at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_events_slide ON slide_events(slide_id);
"""


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on any exception."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Optional[Path] = None) -> None:
    with session(path) as conn:
        conn.executescript(SCHEMA)
