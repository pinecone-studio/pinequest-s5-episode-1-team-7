import pytest

from app.states import ALLOWED, InvalidTransition, SlideState, check_transition


def test_happy_path_is_allowed():
    path = [SlideState.NEW, SlideState.IMAGE_PROCESSING, SlideState.AI_RUNNING, SlideState.SCORED,
            SlideState.QUEUED, SlideState.UNDER_REVIEW, SlideState.ARCHIVED]
    for src, dst in zip(path, path[1:]):
        check_transition(src, dst)


def test_archived_is_terminal():
    assert ALLOWED[SlideState.ARCHIVED] == set()


def test_cannot_skip_ai_stage():
    with pytest.raises(InvalidTransition):
        check_transition(SlideState.NEW, SlideState.QUEUED)


def test_failed_can_only_retry():
    assert ALLOWED[SlideState.FAILED] == {SlideState.NEW}


def test_every_state_has_rules():
    assert set(ALLOWED) == set(SlideState)
