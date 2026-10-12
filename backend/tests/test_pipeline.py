from pathlib import Path

from app import db, ingest, pipeline, queue
from app.states import SlideState
from helpers import make_jpeg


def _slide(color=(120, 20, 160)):
    return ingest.ingest_bytes(make_jpeg(color), "P-1", "Routine")


def _row(sid):
    with db.session() as conn:
        return queue.get_slide(conn, sid)


def test_stub_pipeline_reaches_queue_with_heatmap(env, monkeypatch):
    from app import engine_adapter
    monkeypatch.setattr(pipeline, "load_engine", lambda: engine_adapter._stub_analyze_slide)
    sid = _slide()
    pipeline.process_slide(sid)
    row = _row(sid)
    assert row["state"] == "queued" and row["risk_score"] is not None and row["risk_flag"] in ("red", "yellow", "green")
    assert Path(row["heatmap_path"]) == env / "heatmaps" / f"{sid}.png" and Path(row["heatmap_path"]).is_file()
    assert row["num_patches"] == 1 and row["inference_ms"] is not None


def test_engine_flag_and_metrics_are_stored(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: (lambda p: {"score": 0.1, "risk_flag": "red",
                                                                     "num_patches": 7, "inference_ms": 99.5}))
    sid = _slide()
    pipeline.process_slide(sid)
    row = _row(sid)
    assert row["risk_flag"] == "red" and row["num_patches"] == 7 and row["heatmap_path"] is None


def test_engine_exception_marks_failed(env, monkeypatch):
    def boom(_):
        raise RuntimeError("model file missing")
    monkeypatch.setattr(pipeline, "load_engine", lambda: boom)
    sid = _slide()
    pipeline.process_slide(sid)
    row = _row(sid)
    assert row["state"] == "failed" and "model file missing" in row["error"]


def test_bad_engine_output_marks_failed(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: (lambda p: {"score": 7}))
    sid = _slide()
    pipeline.process_slide(sid)
    assert _row(sid)["state"] == "failed"


def test_missing_heatmap_file_marks_failed(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: (lambda p: {"score": 0.5, "heatmap_path": "/nope.png"}))
    sid = _slide()
    pipeline.process_slide(sid)
    assert _row(sid)["state"] == "failed"


def test_failed_slide_can_be_retried(env, monkeypatch):
    calls = {"n": 0}

    def flaky(_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first run fails")
        return {"score": 0.6}
    monkeypatch.setattr(pipeline, "load_engine", lambda: flaky)
    sid = _slide()
    pipeline.process_slide(sid)
    assert _row(sid)["state"] == "failed"
    with db.session() as conn:
        queue.transition(conn, sid, SlideState.NEW, note="retry", error=None)
    pipeline.process_slide(sid)
    row = _row(sid)
    assert row["state"] == "queued" and row["error"] is None


def test_processing_an_already_queued_slide_does_not_corrupt_it(env, monkeypatch):
    monkeypatch.setattr(pipeline, "load_engine", lambda: (lambda p: {"score": 0.5}))
    sid = _slide()
    pipeline.process_slide(sid)
    pipeline.process_slide(sid)  # duplicate task: invalid transition, must not raise or change state
    assert _row(sid)["state"] == "queued"
