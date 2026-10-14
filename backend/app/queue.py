"""Slide records + triage queue logic (TDD 3.1 steps 2 and 6, TDD 3.2)."""
import sqlite3
from typing import Optional

from . import config
from .states import InvalidTransition, SlideState, check_transition

# Columns transition() is allowed to update besides `state` (guards the dynamic SQL).
_UPDATABLE = {"risk_score", "risk_flag", "priority_override", "heatmap_path",
              "num_patches", "inference_ms", "decision", "error", "scale_warning"}
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"

# Pathologist actions (TDD 6.2)
ACTIONS = {"confirm_malignancy", "mark_benign", "request_biopsy", "reassign_priority"}


def risk_flag(score: Optional[float]) -> Optional[str]:
    """Fallback flag from S_slide thresholds (used when the engine returns none)."""
    if score is None:
        return None
    if score >= config.RED_THRESHOLD:
        return "red"
    if score >= config.YELLOW_THRESHOLD:
        return "yellow"
    return "green"


def _log(conn: sqlite3.Connection, slide_id: int, src: Optional[str], dst: str, note: Optional[str]) -> None:
    conn.execute(
        "INSERT INTO slide_events (slide_id, from_state, to_state, note) VALUES (?,?,?,?)",
        (slide_id, src, dst, note),
    )


def create_slide(conn: sqlite3.Connection, local_hash: str, indication: str, image_path: str,
                 setup_id: Optional[int] = None, objective: Optional[str] = None,
                 um_per_px: Optional[float] = None) -> int:
    cur = conn.execute(
        "INSERT INTO slides (local_hash, indication, state, image_path, setup_id, objective, um_per_px)"
        " VALUES (?,?,?,?,?,?,?)",
        (local_hash, indication, SlideState.NEW.value, image_path, setup_id, objective, um_per_px),
    )
    slide_id = cur.lastrowid
    _log(conn, slide_id, None, SlideState.NEW.value, None)
    return slide_id


def get_slide(conn: sqlite3.Connection, slide_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM slides WHERE id=?", (slide_id,)).fetchone()


def transition(conn: sqlite3.Connection, slide_id: int, dst: SlideState,
               note: Optional[str] = None, **fields) -> None:
    """Move a slide to `dst`: validates against the state machine, updates extra columns, logs an event."""
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"cannot update columns: {sorted(unknown)}")
    row = get_slide(conn, slide_id)
    if row is None:
        raise KeyError(slide_id)
    src = SlideState(row["state"])
    check_transition(src, dst)
    sets = ["state=?", f"updated_at={_NOW}"]
    vals: list = [dst.value]
    for key, val in fields.items():
        sets.append(f"{key}=?")
        vals.append(val)
    # Compare-and-set on the old state so two threads cannot both win the same transition.
    cur = conn.execute(
        f"UPDATE slides SET {', '.join(sets)} WHERE id=? AND state=?",
        [*vals, slide_id, src.value],
    )
    if cur.rowcount != 1:
        raise InvalidTransition("slide state changed concurrently")
    _log(conn, slide_id, src.value, dst.value, note)


def set_score(conn: sqlite3.Connection, slide_id: int, score: float, flag: Optional[str],
              heatmap_path: Optional[str], num_patches: Optional[int] = None,
              inference_ms: Optional[float] = None, scale_warning: Optional[str] = None) -> None:
    """AI_RUNNING -> SCORED -> QUEUED. Ordering of the worklist is done by list_queue()."""
    score = max(0.0, min(1.0, float(score)))
    transition(conn, slide_id, SlideState.SCORED, risk_score=score, risk_flag=flag or risk_flag(score),
               heatmap_path=heatmap_path, num_patches=num_patches, inference_ms=inference_ms,
               scale_warning=scale_warning)
    transition(conn, slide_id, SlideState.QUEUED)


def list_queue(conn: sqlite3.Connection, sort: str = "risk") -> list[sqlite3.Row]:
    """Worklist (state = queued). 'risk' = descending S_slide (manual priority wins); 'time' = oldest first."""
    if sort == "time":
        order = "created_at ASC, id ASC"
    else:
        # A pathologist's explicit override always outranks the AI score, even on ties.
        order = ("(priority_override IS NOT NULL) DESC, "
                 "COALESCE(priority_override, risk_score) DESC, created_at ASC, id ASC")
    return conn.execute(
        f"SELECT * FROM slides WHERE state=? ORDER BY {order}", (SlideState.QUEUED.value,)
    ).fetchall()


def list_all(conn: sqlite3.Connection, state: Optional[str] = None) -> list[sqlite3.Row]:
    if state:
        return conn.execute(
            "SELECT * FROM slides WHERE state=? ORDER BY created_at DESC, id DESC", (state,)).fetchall()
    return conn.execute("SELECT * FROM slides ORDER BY created_at DESC, id DESC").fetchall()


def list_events(conn: sqlite3.Connection, slide_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM slide_events WHERE slide_id=? ORDER BY id", (slide_id,)).fetchall()


def apply_action(conn: sqlite3.Connection, slide_id: int, action: str, priority: Optional[float] = None) -> None:
    """Pathologist actions. confirm/benign/biopsy archive a slide that is UNDER_REVIEW."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    if action != "reassign_priority":
        transition(conn, slide_id, SlideState.ARCHIVED, note=action, decision=action)
        return
    if priority is None or not 0.0 <= priority <= 1.0:
        raise ValueError("priority must be within [0, 1]")
    row = get_slide(conn, slide_id)
    if row is None:
        raise KeyError(slide_id)
    state = SlideState(row["state"])
    if state == SlideState.UNDER_REVIEW:  # hand it back to the worklist with a manual priority
        transition(conn, slide_id, SlideState.QUEUED, note="priority reassigned", priority_override=priority)
    elif state == SlideState.QUEUED:
        conn.execute(f"UPDATE slides SET priority_override=?, updated_at={_NOW} WHERE id=?", (priority, slide_id))
        _log(conn, slide_id, state.value, state.value, "priority reassigned")
    else:
        raise InvalidTransition(f"cannot reassign priority while {state.value}")


def recover_interrupted(conn: sqlite3.Connection) -> int:
    """After a crash / power cut: slides stuck mid-pipeline become FAILED so they can be retried."""
    stuck = (SlideState.NEW, SlideState.IMAGE_PROCESSING, SlideState.AI_RUNNING, SlideState.SCORED)
    rows = conn.execute(
        f"SELECT id FROM slides WHERE state IN ({','.join('?' * len(stuck))})", [s.value for s in stuck]
    ).fetchall()
    for r in rows:
        transition(conn, r["id"], SlideState.FAILED, note="interrupted by restart", error="interrupted by restart")
    return len(rows)
