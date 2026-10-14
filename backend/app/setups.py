"""Microscope + phone setup profiles for magnification calibration (issue #35).

One row per physical setup (microscope + phone + adapter): the technician photographs
a stage micrometer once and the app stores µm/px at the objective used. µm/px scales
with objective power, so one calibration covers all objectives:

    um_per_px(obj) = um_per_px(calibrated) × obj_calibrated / obj
"""
import math
import re
import sqlite3
from typing import Optional

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"


def parse_magnification(objective: str) -> float:
    """'40x' (or '40X', ' 40 x') -> 40.0. Raises ValueError for anything else."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*x\s*", objective or "", re.IGNORECASE)
    if not match:
        raise ValueError(f"objective must look like '10x', '20x' or '40x', got {objective!r}")
    mag = float(match.group(1))
    if mag <= 0:
        raise ValueError(f"objective magnification must be positive, got {objective!r}")
    return mag


def _validate(name: str, um_per_px: float, calibration_objective: str) -> tuple[str, float, float]:
    name = (name or "").strip()
    if not name:
        raise ValueError("setup name must not be empty")
    try:
        um = float(um_per_px)
    except (TypeError, ValueError) as exc:
        raise ValueError("um_per_px must be a number") from exc
    if not math.isfinite(um) or um <= 0:
        raise ValueError("um_per_px must be a positive number")
    return name, um, parse_magnification(calibration_objective)


def create_setup(conn: sqlite3.Connection, name: str, um_per_px: float,
                 calibration_objective: str, phone_resolution: Optional[str] = None) -> int:
    """Store a calibrated setup. Raises ValueError on bad input or a duplicate name."""
    name, um, _ = _validate(name, um_per_px, calibration_objective)
    try:
        cur = conn.execute(
            f"INSERT INTO setups (name, um_per_px, calibration_objective, phone_resolution) "
            f"VALUES (?,?,?,?)",
            (name, um, calibration_objective.strip(), (phone_resolution or "").strip() or None),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"a setup named {name!r} already exists") from exc
    return cur.lastrowid


def get_setup(conn: sqlite3.Connection, setup_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM setups WHERE id=?", (setup_id,)).fetchone()


def list_setups(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM setups ORDER BY name, id").fetchall()


def delete_setup(conn: sqlite3.Connection, setup_id: int) -> None:
    """Delete a setup. Raises KeyError when missing, ValueError while slides still use it."""
    if get_setup(conn, setup_id) is None:
        raise KeyError(setup_id)
    try:
        conn.execute("DELETE FROM setups WHERE id=?", (setup_id,))
    except sqlite3.IntegrityError as exc:
        raise ValueError("setup is still used by existing slides") from exc


def um_per_px_for(conn: sqlite3.Connection, setup_id: int, objective: Optional[str] = None) -> float:
    """µm/px for a capture: the setup's calibrated value scaled to `objective`.

    No objective means the photo was taken at the calibration objective.
    Raises KeyError for an unknown setup, ValueError for a bad objective.
    """
    row = get_setup(conn, setup_id)
    if row is None:
        raise KeyError(setup_id)
    if objective is None:
        return float(row["um_per_px"])
    return float(row["um_per_px"]) * parse_magnification(row["calibration_objective"]) / parse_magnification(objective)
