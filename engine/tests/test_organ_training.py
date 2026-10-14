"""Training code for other organs' datasets (issue #53). Skipped without the training extras."""
import numpy as np
import pytest

pytest.importorskip("torch")
h5py = pytest.importorskip("h5py")
pytest.importorskip("pyarrow")
pytest.importorskip("sklearn")

from training import download_nct_crc as nct  # noqa: E402
from training import plism_eval, teacher, tune_scoring  # noqa: E402
from training.pcam import DATASETS, PCamBatches, split_paths  # noqa: E402


def test_split_paths_per_dataset(tmp_path):
    assert split_paths("train", tmp_path)[0].name == "camelyonpatch_level_2_split_train_x.h5"  # PCam unchanged
    x, y = split_paths("test", tmp_path, "nct_crc")
    assert (x.name, y.name) == ("nct_crc_split_test_x.h5", "nct_crc_split_test_y.h5")
    assert split_paths("valid", dataset="nct_crc")[0].parent == DATASETS["nct_crc"]["dir"]


def test_heldout_halves_split_every_class_in_half():
    classes = np.repeat(np.arange(9, dtype=np.uint8), [10, 11, 3, 4, 5, 6, 7, 8, 21])
    valid, test = nct.heldout_halves(classes)

    assert len(np.intersect1d(valid, test)) == 0
    assert len(valid) + len(test) == len(classes)
    for c in range(9):
        n_valid, n_test = (np.sum(classes[idx] == c) for idx in (valid, test))
        assert abs(int(n_valid) - int(n_test)) <= 1
    np.testing.assert_array_equal(nct.heldout_halves(classes)[0], valid)  # fixed seed


def test_write_split_stores_tumour_label_and_class(tmp_path):
    rng = np.random.default_rng(0)
    images = rng.integers(0, 255, (5, nct.TILE, nct.TILE, 3), dtype=np.uint8)
    classes = np.array([nct.TUMOUR, 0, 6, nct.TUMOUR, 7], dtype=np.uint8)
    batches = [(images[:2], classes[:2]), (images[2:], classes[2:])]

    nct.write_split("valid", batches, 5, tmp_path)

    data = PCamBatches.from_split("valid", tmp_path, dataset="nct_crc")
    x, y = data[[0, 1, 2, 3, 4]]
    np.testing.assert_array_equal(x.numpy(), images)
    np.testing.assert_array_equal(y.numpy(), [1, 0, 0, 1, 0])
    with h5py.File(split_paths("valid", tmp_path, "nct_crc")[1]) as f:
        np.testing.assert_array_equal(f["cls"][:], classes)
        assert f.attrs["classes"].split(",")[nct.TUMOUR] == "TUM"


def test_write_split_rejects_a_short_split(tmp_path):
    images = np.zeros((2, nct.TILE, nct.TILE, 3), dtype=np.uint8)
    with pytest.raises(RuntimeError, match="expected 3 images, got 2"):
        nct.write_split("test", [(images, np.zeros(2, dtype=np.uint8))], 3, tmp_path)
    assert not any(tmp_path.iterdir())  # no partial files left behind


def test_shuffle_split_keeps_images_with_their_labels_and_runs_once(tmp_path):
    n = 12
    classes = np.repeat(np.arange(3, dtype=np.uint8), 4)  # sorted by class, like the sources
    classes[-4:] = nct.TUMOUR
    images = np.zeros((n, nct.TILE, nct.TILE, 3), dtype=np.uint8)
    images[:, 0, 0, 0] = np.arange(n)  # tag each image with its original index
    nct.write_split("train", [(images, classes)], n, tmp_path)

    nct.shuffle_split("train", tmp_path, chunk=5)
    x, y = PCamBatches.from_split("train", tmp_path, dataset="nct_crc")[list(range(n))]
    original = x.numpy()[:, 0, 0, 0]
    assert sorted(original) == list(range(n)) and list(original) != list(range(n))
    np.testing.assert_array_equal(y.numpy(), (classes[original] == nct.TUMOUR).astype(np.float32))

    nct.shuffle_split("train", tmp_path)  # already shuffled: unchanged
    x2, _ = PCamBatches.from_split("train", tmp_path, dataset="nct_crc")[list(range(n))]
    np.testing.assert_array_equal(x2.numpy(), x.numpy())


def test_teacher_files_keep_pcam_names_and_separate_other_datasets():
    assert teacher.head_path("hibou-b").name == "teacher_hibou-b_head.pt"  # the committed head
    assert teacher.features_path("hibou-b", "train").name == "teacher_hibou-b_train.npz"
    assert teacher.head_path("hibou-b", "nct_crc").name == "teacher_hibou-b_nct_crc_head.pt"
    assert teacher.features_path("hibou-b", "valid", "nct_crc").name == "teacher_hibou-b_nct_crc_valid.npz"


def test_slide_scoring_results_per_organ():
    assert tune_scoring.results_path("pcam").name == "slide_scoring.json"
    assert tune_scoring.results_path("nct_crc").name == "slide_scoring_colon.json"


def test_plism_summary_reports_the_organs_own_tissues():
    rows, scores = [], {}
    spots = [("04_right_colon", [0.1, 0.2, 0.6, 0.3]), ("34_colon_adenocarcionma", [0.9, 0.8, 0.4, 0.7]),
             ("12_lymph_node", [0.1, 0.1, 0.1, 0.1])]
    for i, (tissue, probs) in enumerate(spots):
        rows.append({"stain": "GIVH", "device": "GT450", "coordinate": str(i), "tissue_type": tissue})
        scores[("GIVH", "GT450", str(i))] = (np.array(probs), 100.0)

    organ = plism_eval.summarise(rows, scores, "colon")["GT450"]["organ"]

    assert organ["normal_false_alarm"] == 0.25
    assert organ["cancer_flagged"] == 0.75
    assert organ["patches"] == {"normal": 4, "cancer": 4}
    assert 0.5 < organ["cancer_vs_normal_auc"] <= 1.0
    assert "organ" not in plism_eval.summarise(rows, scores)["GT450"]  # unchanged without --organ


def test_hmu_gc_splits_are_disjoint_number_ranges_with_gaps():
    from training import download_hmu_gc as hmu

    members = {s: hmu.split_members(s) for s in hmu.RANGES}
    numbers = {s: {n for _, n in m} for s, m in members.items()}
    assert max(numbers["train"]) + hmu.GAP < min(numbers["valid"])
    assert max(numbers["valid"]) + hmu.GAP < min(numbers["test"])
    assert max(numbers["test"]) == hmu.PER_CLASS
    for split, m in members.items():  # every class gets the same number range
        per_class = np.bincount([c for c, _ in m], minlength=len(hmu.CLASSES))
        assert len(set(per_class)) == 1, split


def test_shuffle_split_keeps_extra_label_arrays_aligned(tmp_path):
    from training import download_hmu_gc as hmu

    n = 6
    images = np.zeros((n, nct.TILE, nct.TILE, 3), dtype=np.uint8)
    images[:, 0, 0, 0] = np.arange(n)
    classes = np.array([7, 0, 7, 1, 2, 3], dtype=np.uint8)
    nct.write_split("valid", [(images, classes)], n, tmp_path, "hmu_gc", hmu.CLASSES)
    with h5py.File(split_paths("valid", tmp_path, "hmu_gc")[1], "a") as f:
        f.create_dataset("idx", data=np.arange(100, 100 + n))

    nct.shuffle_split("valid", tmp_path, dataset="hmu_gc")

    x, y = PCamBatches.from_split("valid", tmp_path, dataset="hmu_gc")[list(range(n))]
    original = x.numpy()[:, 0, 0, 0]
    with h5py.File(split_paths("valid", tmp_path, "hmu_gc")[1]) as f:
        np.testing.assert_array_equal(f["idx"][:], 100 + original)
        np.testing.assert_array_equal(f["cls"][:], classes[original])
        assert f.attrs["classes"].split(",") == list(hmu.CLASSES)
    np.testing.assert_array_equal(y.numpy(), (classes[original] == 7).astype(np.float32))  # TUM is index 7
