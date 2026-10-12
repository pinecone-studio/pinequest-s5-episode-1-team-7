import numpy as np
import pytest

from pipeline.scoring import (
    RED_THRESHOLD,
    YELLOW_THRESHOLD,
    logit,
    risk_flag,
    slide_logit,
    slide_score,
    to_score,
)


def probs_from_logits(*z):
    return 1.0 / (1.0 + np.exp(-np.array(z, dtype=np.float64)))


def test_slide_logit_mixes_max_and_top_k_mean():
    probs = probs_from_logits(4.0, 2.0, 0.0, -2.0, -6.0)

    assert slide_logit(probs, w_max=1.0, top_k=3) == pytest.approx(4.0)
    assert slide_logit(probs, w_max=0.0, top_k=3) == pytest.approx(2.0)   # mean(4, 2, 0)
    assert slide_logit(probs, w_max=0.5, top_k=3) == pytest.approx(3.0)


def test_top_k_larger_than_slide_uses_all_patches():
    assert slide_logit(probs_from_logits(1.0, 3.0), w_max=0.0, top_k=10) == pytest.approx(2.0)


def test_one_stray_patch_does_not_dominate_with_default_weights():
    normal = probs_from_logits(*[-5.0] * 199)
    one_artifact = np.r_[normal, probs_from_logits(12.0)]
    real_focus = np.r_[normal[:-2], probs_from_logits(12.0, 11.0, 10.0)]

    assert slide_score(one_artifact) < slide_score(real_focus)
    assert risk_flag(slide_score(one_artifact)) == "green"
    assert risk_flag(slide_score(real_focus)) == "red"


def test_score_is_in_unit_interval_and_monotonic():
    z = np.linspace(-40, 40, 101)
    s = to_score(z)

    assert ((s >= 0) & (s <= 1)).all()
    assert (np.diff(s) > 0).all()
    assert to_score(0.0) == pytest.approx(0.5)


def test_saturated_probabilities_stay_finite():
    assert np.isfinite(logit(np.array([0.0, 1.0]))).all()
    assert 0.0 < slide_score(np.array([1.0, 1.0, 1.0])) < 1.0


def test_no_patches_scores_zero():
    assert slide_score(np.zeros(0)) == 0.0
    assert risk_flag(0.0) == "green"


@pytest.mark.parametrize(
    ("score", "flag"),
    [(RED_THRESHOLD, "red"), (0.99, "red"), (YELLOW_THRESHOLD, "yellow"), (RED_THRESHOLD - 1e-6, "yellow"),
     (YELLOW_THRESHOLD - 1e-6, "green"), (0.1, "green")],
)
def test_risk_flag_thresholds(score, flag):
    assert risk_flag(score) == flag


def test_thresholds_are_ordered():
    assert 0.0 < YELLOW_THRESHOLD < RED_THRESHOLD < 1.0
