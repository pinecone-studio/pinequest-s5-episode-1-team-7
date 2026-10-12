import numpy as np
import pytest

from pipeline import inference
from pipeline.inference import PatchClassifier, get_classifier

TISSUE = (200, 120, 180)
WHITE = (245, 245, 245)


def patches(*colours, size=224):
    return np.stack([np.full((size, size, 3), c, dtype=np.uint8) for c in colours])


def test_scores_one_probability_per_patch(tiny_model):
    clf = PatchClassifier(tiny_model)

    probs = clf.predict(patches(TISSUE, WHITE))

    assert probs.dtype == np.float32 and probs.shape == (2,)
    np.testing.assert_allclose(probs, [0.757, 0.119], atol=0.01)


def test_resizes_patches_to_model_input(tiny_model):
    clf = PatchClassifier(tiny_model)
    assert clf.input_size == 32

    for size in (224, 16):  # shrink and enlarge
        np.testing.assert_allclose(clf.predict(patches(TISSUE, size=size)), [0.757], atol=0.01)


def test_batches_give_same_result_as_one_pass(tiny_model):
    rng = np.random.default_rng(0)
    many = rng.integers(0, 256, (37, 32, 32, 3), dtype=np.uint8)

    batched = PatchClassifier(tiny_model, batch_size=8).predict(many)
    single = PatchClassifier(tiny_model, batch_size=64).predict(many)

    np.testing.assert_allclose(batched, single, rtol=1e-6)


def test_empty_input_gives_empty_output(tiny_model):
    out = PatchClassifier(tiny_model).predict(np.zeros((0, 224, 224, 3), dtype=np.uint8))
    assert out.shape == (0,)


def test_rejects_non_rgb_patches(tiny_model):
    with pytest.raises(ValueError):
        PatchClassifier(tiny_model).predict(np.zeros((1, 224, 224), dtype=np.uint8))


def test_missing_model_explains_how_to_get_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="TRIAGE_MODEL_PATH"):
        PatchClassifier(tmp_path / "missing.onnx")


def test_falls_back_to_cpu_when_preferred_provider_is_unavailable(tiny_model):
    clf = PatchClassifier(tiny_model, providers=("NoSuchExecutionProvider", "CPUExecutionProvider"))
    assert clf.provider == "CPUExecutionProvider"


def test_falls_back_when_a_provider_fails_to_start(tiny_model, monkeypatch):
    import onnxruntime as ort

    real_session = ort.InferenceSession

    def flaky_session(path, options, providers):
        if providers[0] == "DmlExecutionProvider":
            raise RuntimeError("GPU driver error")
        return real_session(path, options, providers=providers)

    monkeypatch.setattr(ort, "get_available_providers", lambda: ["DmlExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setattr(ort, "InferenceSession", flaky_session)

    assert PatchClassifier(tiny_model).provider == "CPUExecutionProvider"


def test_get_classifier_loads_once_per_model_path(tiny_model):
    inference._cached_classifier.cache_clear()

    assert get_classifier() is get_classifier()
    assert get_classifier().input_size == 32
