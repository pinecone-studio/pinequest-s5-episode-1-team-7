import numpy as np
import pytest

from pipeline.scale import MODEL_UM_PER_PX, rescale_factor, to_model_scale


def test_rescale_factor():
    assert rescale_factor(MODEL_UM_PER_PX) == 1.0
    assert rescale_factor(0.84) == pytest.approx(2.0)
    assert rescale_factor(np.float32(0.21)) == pytest.approx(0.5)


@pytest.mark.parametrize("bad", [0, -0.3, float("nan"), float("inf"), 0.01, 3.0, "0.4x", None, True])
def test_rescale_factor_rejects_implausible_values(bad):
    with pytest.raises(ValueError):
        rescale_factor(bad)


def test_to_model_scale_shrinks_high_magnification_photo():
    image = np.zeros((800, 1000, 3), dtype=np.uint8)  # e.g. 40x objective, ~0.25 µm/px

    assert to_model_scale(image, 0.21).shape == (400, 500, 3)


def test_to_model_scale_enlarges_low_magnification_photo():
    image = np.zeros((100, 150, 3), dtype=np.uint8)

    assert to_model_scale(image, 0.84).shape == (200, 300, 3)


def test_to_model_scale_at_model_scale_is_unchanged():
    image = np.zeros((10, 20, 3), dtype=np.uint8)

    assert to_model_scale(image, MODEL_UM_PER_PX) is image
