"""Slide state machine - TDD section 3.2."""
from enum import Enum


class SlideState(str, Enum):
    NEW = "new"                          # New Slide
    IMAGE_PROCESSING = "image_processing"
    AI_RUNNING = "ai_running"            # AI Model Running
    SCORED = "scored"                    # Risk Score Calculated
    QUEUED = "queued"                    # Priority Queue
    UNDER_REVIEW = "under_review"        # Doctor Selection
    ARCHIVED = "archived"                # Reviewed & Archived
    FAILED = "failed"


ALLOWED: dict[SlideState, set[SlideState]] = {
    SlideState.NEW: {SlideState.IMAGE_PROCESSING, SlideState.FAILED},
    SlideState.IMAGE_PROCESSING: {SlideState.AI_RUNNING, SlideState.FAILED},
    SlideState.AI_RUNNING: {SlideState.SCORED, SlideState.FAILED},
    SlideState.SCORED: {SlideState.QUEUED, SlideState.FAILED},
    SlideState.QUEUED: {SlideState.UNDER_REVIEW},
    SlideState.UNDER_REVIEW: {SlideState.ARCHIVED, SlideState.QUEUED},
    SlideState.ARCHIVED: set(),
    SlideState.FAILED: {SlideState.NEW},  # retry
}


class InvalidTransition(Exception):
    pass


def check_transition(src: SlideState, dst: SlideState) -> None:
    if dst not in ALLOWED[src]:
        raise InvalidTransition(f"{src.value} -> {dst.value} is not allowed")
