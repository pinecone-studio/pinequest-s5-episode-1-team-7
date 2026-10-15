import pytest

from app import db, queue
from app.states import InvalidTransition, SlideState


def _queued(conn, score, flag=None, indication="Routine"):
    sid = queue.create_slide(conn, "h", indication, "/tmp/x.jpg")
    queue.transition(conn, sid, SlideState.IMAGE_PROCESSING)
    queue.transition(conn, sid, SlideState.AI_RUNNING)
    queue.set_score(conn, sid, score, flag, None, 12, 340.5)
    return sid


def test_queue_sorted_descending_by_risk(env):
    with db.session() as conn:
        low, high, mid = _queued(conn, 0.1), _queued(conn, 0.9), _queued(conn, 0.5)
        assert [r["id"] for r in queue.list_queue(conn)] == [high, mid, low]


def test_queue_time_sort_is_oldest_first(env):
    with db.session() as conn:
        a, b, c = _queued(conn, 0.9), _queued(conn, 0.1), _queued(conn, 0.5)
        assert [r["id"] for r in queue.list_queue(conn, "time")] == [a, b, c]


def test_risk_flags_fallback():
    assert queue.risk_flag(0.9) == "red"
    assert queue.risk_flag(0.5) == "yellow"
    assert queue.risk_flag(0.1) == "green"
    assert queue.risk_flag(None) is None


def test_engine_flag_wins_over_threshold(env):
    with db.session() as conn:
        sid = _queued(conn, 0.1, flag="red")
        assert queue.get_slide(conn, sid)["risk_flag"] == "red"


def test_metrics_are_stored(env):
    with db.session() as conn:
        sid = _queued(conn, 0.5)
        row = queue.get_slide(conn, sid)
        assert row["num_patches"] == 12 and row["inference_ms"] == 340.5


def test_invalid_transition_rejected(env):
    with db.session() as conn:
        sid = queue.create_slide(conn, "h", "Routine", "/tmp/x.jpg")
        with pytest.raises(InvalidTransition):
            queue.transition(conn, sid, SlideState.QUEUED)


def test_unknown_column_rejected(env):
    with db.session() as conn:
        sid = queue.create_slide(conn, "h", "Routine", "/tmp/x.jpg")
        with pytest.raises(ValueError):
            queue.transition(conn, sid, SlideState.IMAGE_PROCESSING, image_path="/etc/passwd")


def test_review_flow_and_archive(env):
    with db.session() as conn:
        sid = _queued(conn, 0.8)
        queue.transition(conn, sid, SlideState.UNDER_REVIEW)
        assert queue.list_queue(conn) == []
        queue.apply_action(conn, sid, "confirm_malignancy")
        row = queue.get_slide(conn, sid)
        assert row["state"] == "archived" and row["decision"] == "confirm_malignancy"


def test_action_requires_review_first(env):
    with db.session() as conn:
        sid = _queued(conn, 0.8)
        with pytest.raises(InvalidTransition):
            queue.apply_action(conn, sid, "mark_benign")


def test_reassign_priority_reorders(env):
    with db.session() as conn:
        a, b = _queued(conn, 0.9), _queued(conn, 0.2)
        queue.apply_action(conn, b, "reassign_priority", 0.99)
        assert [r["id"] for r in queue.list_queue(conn)] == [b, a]


def test_reassigned_priority_ranks_like_a_score(env):
    with db.session() as conn:
        top, mid, sid = _queued(conn, 0.9), _queued(conn, 0.6), _queued(conn, 0.3)
        queue.apply_action(conn, sid, "reassign_priority", 0.75)   # high: between the two AI slides
        assert [r["id"] for r in queue.list_queue(conn)] == [top, sid, mid]
        queue.apply_action(conn, sid, "reassign_priority", 0.25)   # back to low: below both again
        assert [r["id"] for r in queue.list_queue(conn)] == [top, mid, sid]


def test_reassigned_priority_wins_a_tie_with_the_ai_score(env):
    with db.session() as conn:
        ai, manual = _queued(conn, 0.75), _queued(conn, 0.2)
        queue.apply_action(conn, manual, "reassign_priority", 0.75)
        assert [r["id"] for r in queue.list_queue(conn)] == [manual, ai]


def test_reassign_from_review_returns_to_queue(env):
    with db.session() as conn:
        sid = _queued(conn, 0.2)
        queue.transition(conn, sid, SlideState.UNDER_REVIEW)
        queue.apply_action(conn, sid, "reassign_priority", 0.95)
        row = queue.get_slide(conn, sid)
        assert row["state"] == "queued" and row["priority_override"] == 0.95


def test_reassign_validates_input_and_state(env):
    with db.session() as conn:
        sid = _queued(conn, 0.5)
        with pytest.raises(ValueError):
            queue.apply_action(conn, sid, "reassign_priority", 1.5)
        with pytest.raises(ValueError):
            queue.apply_action(conn, sid, "reassign_priority", None)
        with pytest.raises(ValueError):
            queue.apply_action(conn, sid, "delete_everything")
        queue.transition(conn, sid, SlideState.UNDER_REVIEW)
        queue.apply_action(conn, sid, "mark_benign")
        with pytest.raises(InvalidTransition):
            queue.apply_action(conn, sid, "reassign_priority", 0.5)


def test_score_is_clamped(env):
    with db.session() as conn:
        sid = _queued(conn, 5.0)
        assert queue.get_slide(conn, sid)["risk_score"] == 1.0


def test_events_are_logged(env):
    with db.session() as conn:
        sid = _queued(conn, 0.5)
        states = [e["to_state"] for e in queue.list_events(conn, sid)]
        assert states == ["new", "image_processing", "ai_running", "scored", "queued"]


def test_recover_interrupted_marks_failed_and_allows_retry(env):
    with db.session() as conn:
        stuck = queue.create_slide(conn, "h", "Routine", "/tmp/x.jpg")
        queue.transition(conn, stuck, SlideState.IMAGE_PROCESSING)
        done = _queued(conn, 0.5)
        assert queue.recover_interrupted(conn) == 1
        assert queue.get_slide(conn, stuck)["state"] == "failed"
        assert queue.get_slide(conn, done)["state"] == "queued"
        queue.transition(conn, stuck, SlideState.NEW, note="retry", error=None)
        row = queue.get_slide(conn, stuck)
        assert row["state"] == "new" and row["error"] is None
