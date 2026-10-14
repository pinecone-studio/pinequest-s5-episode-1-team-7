"""Generate the committed model card (engine/model/model_card.json).

The card is the evidence behind the frontend's "About the AI" page: every
number comes from a results file, the model file, or the pipeline constants,
and the generator FAILS when they disagree — so the card cannot drift from
the evidence. Re-run whenever the model, the thresholds, or any results file
changes, and commit the card with them::

    python -m training.make_model_card            # from engine/
    python -m training.make_model_card --check    # CI: exit 1 when the committed card is stale

Needs ``onnx`` (engine/requirements.txt, generator only) for the parameter
count and the export metadata baked into model_fp32.onnx.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_ROOT = HERE.parent
MODEL_DIR = ENGINE_ROOT / "model"
RESULTS = ENGINE_ROOT / "training" / "results"

SHIPPED_FILE = "model_fp32.onnx"
CARD_PATH = MODEL_DIR / "model_card.json"

MAIN_RESULTS = "pcam_mobilenet_v3_small_224_kd-hibou.json"
DIRECT_RESULTS = "pcam_mobilenet_v3_small_224.json"
SMALL_RESULTS = "pcam_mobilenet_v3_small_96.json"
TEACHER_RESULTS = "teacher_hibou-b.json"
SCORING_RESULTS = "slide_scoring.json"
PLISM_RESULTS = "plism_model_fp32_kd-hibou.json"
PLISM_DIRECT_RESULTS = "plism_model_fp32.json"
INT8_RESULTS = "int8_minmax_fp32convs10_pc_rr.json"

# PLISM image scale that matches the training magnification (issue #35).
PLISM_GOOD_SCALE = "0.6"


def _load(name: str) -> dict:
    with open(RESULTS / name) as f:
        return json.load(f)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_date(path: Path) -> str | None:
    """Commit date of `path` (when its numbers entered the repo), or None outside git."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ENGINE_ROOT.parent), "log", "-1", "--format=%cI", "--", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(ENGINE_ROOT.parent), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _onnx_facts(path: Path) -> dict:
    """Size, hash, parameter count and export metadata of the shipped weights."""
    try:
        import onnx
    except ImportError as exc:
        raise SystemExit("make_model_card needs the 'onnx' package (engine/requirements.txt)") from exc
    model = onnx.load(str(path))
    params = 0
    for init in model.graph.initializer:
        n = 1
        for dim in init.dims:
            n *= dim
        params += n
    return {
        "params": params,
        "metadata": {prop.key: prop.value for prop in model.metadata_props},
    }


def _device_table(plism: dict) -> tuple[dict, dict]:
    """{name: lymph-node false-alarm share} at the correct magnification, by kind."""
    scanners, phones = {}, {}
    for name, row in plism["by_scale"][PLISM_GOOD_SCALE].items():
        (scanners if row["kind"] == "scanner" else phones)[name] = round(row["lymph_node_false_alarm"], 4)
    return scanners, phones


def build_card() -> dict:
    main = _load(MAIN_RESULTS)
    direct = _load(DIRECT_RESULTS)
    small = _load(SMALL_RESULTS)
    teacher = _load(TEACHER_RESULTS)
    scoring = _load(SCORING_RESULTS)
    plism = _load(PLISM_RESULTS)
    int8 = _load(INT8_RESULTS)
    model_path = MODEL_DIR / SHIPPED_FILE
    if not model_path.is_file():
        raise SystemExit(f"shipped model missing: {model_path}")
    facts = _onnx_facts(model_path)

    # The card must describe exactly these weights: the export metadata baked
    # into the ONNX file has to agree with the training results it came from.
    meta = facts["metadata"]
    assert abs(float(meta["test_auc"]) - round(main["test"]["auc"], 4)) < 1e-9, \
        f"ONNX test_auc {meta['test_auc']} != {MAIN_RESULTS} test.auc {main['test']['auc']:.4f}"
    assert meta.get("distilled_from") == main.get("teacher"), \
        f"ONNX distilled_from {meta.get('distilled_from')} != {MAIN_RESULTS} teacher {main.get('teacher')}"
    assert meta.get("input_size") == str(main["config"]["img_size"]) == "224"

    # Thresholds in code must be the tuned ones (rounded to 2 dp in scoring.py).
    sys.path.insert(0, str(ENGINE_ROOT))
    from pipeline import MODEL_UM_PER_PX
    from pipeline.scoring import RED_THRESHOLD, TEMPERATURE, TOP_K, W_MAX, YELLOW_THRESHOLD
    chosen = scoring["chosen"]
    assert (W_MAX, TOP_K) == (chosen["w_max"], chosen["top_k"]), "scoring formula != tuned choice"
    assert (round(chosen["red"], 2), round(chosen["yellow"], 2)) == (RED_THRESHOLD, YELLOW_THRESHOLD), \
        "scoring thresholds != tuned choice"
    assert scoring.get("model") == SHIPPED_FILE, "slide_scoring.json is not for the shipped file"

    from pipeline.inference import PREFERRED_PROVIDERS

    test = main["test"]
    at90 = main["evaluation"]["tta1"]["test_at_val_90_sensitivity"]
    scanners, phones = _device_table(plism)
    other_fa = [round(row["normal_tissue_false_alarm"], 4)
                for row in plism["by_scale"][PLISM_GOOD_SCALE].values() if row["kind"] == "phone"]
    size_bytes = model_path.stat().st_size

    slide_test = scoring["test"]
    fractions = {frac: {"auc": round(slide_test[frac]["auc"], 4) if "auc" in slide_test[frac] else None,
                        "red": slide_test[frac]["red"],
                        "yellow_or_red": slide_test[frac]["yellow_or_red"]}
                 for frac in ("tumour_1pct", "tumour_2pct", "tumour_5pct", "tumour_10pct", "tumour_25pct")}
    try:
        tuned_commit = subprocess.run(
            ["git", "-C", str(ENGINE_ROOT.parent), "log", "-1", "--format=%H",
             "--", str(RESULTS / SCORING_RESULTS)],
            capture_output=True, text=True, check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        tuned_commit = None

    return {
        "name": "PCam MobileNetV3-Small, Hibou-B-distilled",
        "version": SHIPPED_FILE,
        "file": {
            "name": SHIPPED_FILE,
            "sha256": _sha256(model_path),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1e6, 2),
            "committed": _git_date(model_path),
        },
        "architecture": {
            "name": "MobileNetV3-Small",
            "params": facts["params"],
            "input_px": main["config"]["img_size"],
            "input_scale_um_per_px": MODEL_UM_PER_PX,
        },
        "provenance": {
            "dataset": main["dataset"],
            "backbone": "ImageNet-pretrained MobileNetV3-Small",
            "training": f"fine-tuned on PCam ({main['config']['epochs']} epochs, best epoch {main['best_epoch']}, "
                        f"strong augmentation + EMA, {main['config']['batch_size']}-batch)",
            "distilled_from": f"{main['teacher']} (foundation model, histai/hibou-b)",
            "date_trained": _git_date(RESULTS / MAIN_RESULTS),
            "export_metadata": {k: meta[k] for k in ("arch", "dataset", "val_auc", "test_auc", "test_accuracy",
                                                     "distilled_from") if k in meta},
        },
        "runtime": {
            "offline": True,
            "runs_on": "this clinic PC only: no cloud, no data leaves the clinic (TDD 1.2, 7.1)",
            "providers_preference": list(PREFERRED_PROVIDERS),
            "measured_per_slide_s": {
                "value": int8["fp32"]["seconds_per_slide"],
                "context": "median warmed run, 150 patches, batch 16, 4 threads, i5-13400F "
                           f"({int8['benchmark']}). Same-graph reference: the distilled student "
                           "is the same MobileNetV3-Small graph as the measured direct model.",
            },
        },
        "patch_metrics": {
            "split": f"PCam test (n={test['n']:,})",
            "threshold": test["threshold"],
            "auc": round(test["auc"], 4),
            "accuracy": round(test["accuracy"], 4),
            "sensitivity": round(test["sensitivity"], 4),
            "specificity": round(test["specificity"], 4),
            "at_90_sensitivity": {
                "threshold": round(at90["threshold"], 4),
                "sensitivity": round(at90["sensitivity"], 4),
                "specificity": round(at90["specificity"], 4),
            },
        },
        "slide_metrics": {
            "formula": f"sigmoid(mean(top-{TOP_K} patch log-odds) / {TEMPERATURE:g})",
            "thresholds": {"red": RED_THRESHOLD, "yellow": YELLOW_THRESHOLD},
            "tuned": _git_date(RESULTS / SCORING_RESULTS),
            "tuned_commit": tuned_commit,
            "normal_slides": {"red": slide_test["normal_slides"]["red"],
                              "yellow_or_red": slide_test["normal_slides"]["yellow_or_red"]},
            "tumour_fractions": fractions,
        },
        "plism": {
            "at": f"{PLISM_GOOD_SCALE}x (≈0.42 µm/px, the training magnification, issue #35)",
            "source": f"{PLISM_RESULTS} (evaluated as model_fp32_kd-hibou.onnx: the same distilled "
                      "weights later shipped as model_fp32.onnx)",
            "metric": "share of normal lymph-node patches flagged (P ≥ 0.5)",
            "scanners": scanners,
            "phones": phones,
            "other_tissues_false_alarm": {"min": min(other_fa), "max": max(other_fa),
                                          "note": "normal non-lymph tissue on phones: not valid, see limitations"},
        },
        "comparison": [
            {"model": "MobileNetV3-Small, Hibou-B-distilled (shipped)",
             "pcam_auc": round(test["auc"], 4), "size_mb": round(size_bytes / 1e6, 2),
             "per_slide_s": int8["fp32"]["seconds_per_slide"], "note": "same-graph speed reference, see runtime"},
            {"model": "MobileNetV3-Small, direct (previous release)",
             "pcam_auc": round(direct["test"]["auc"], 4), "size_mb": int8["fp32"]["size_mb"],
             "per_slide_s": int8["fp32"]["seconds_per_slide"], "note": "replaced: worse PLISM phone agreement"},
            {"model": "Hibou-B foundation-model teacher (head only)",
             "pcam_auc": round(teacher["test_auc"], 4), "size_mb": None,
             "per_slide_s": None, "note": "training-time teacher, too large for clinic PCs"},
            {"model": "MobileNetV3-Small 96 px (study)",
             "pcam_auc": round(small["test"]["auc"], 4), "size_mb": None,
             "per_slide_s": None, "note": "native-PCam-size study, never exported"},
            {"model": "INT8-quantized direct model (study)",
             "pcam_auc": int8["int8"]["test_auc"], "size_mb": int8["int8"]["size_mb"],
             "per_slide_s": int8["int8"]["seconds_per_slide"],
             "note": "72% smaller but slower than FP32 on CPU → not shipped"},
        ],
        "literature": {
            "note": "Published PCam baselines were not recorded with these runs, so none are quoted: "
                    "numbers here come only from the evidence files above.",
            "baselines": [],
        },
        "limitations": [
            f"Trained only on lymph-node metastases (breast cancer, PCam). Not valid for other organs: "
            f"normal non-lymph tissue false alarms were {min(other_fa):.0%}–{max(other_fa):.0%} on phones "
            f"at the correct magnification (PLISM).",
            "Needs a calibrated magnification (issue #35): at captured scale the same phones falsely "
            "flagged 42–74% of normal lymph-node patches; 0–9% at 0.6x. Always capture with a setup + objective.",
            "Slide thresholds were tuned on slides simulated from PCam validation patches "
            "(normal slides: 0.4% red, 5.8% yellow-or-red on test); re-tune on real captures.",
            "Prioritisation aid only, not a diagnostic engine: every slide must be reviewed by a "
            "pathologist (TDD 1.2).",
        ],
        "generated": {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "repo_commit": _git_head(),
            "generator": "training/make_model_card.py",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate engine/model/model_card.json from the evidence files.")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when the committed card differs (ignoring the generation stamp)")
    args = parser.parse_args(argv)
    card = build_card()
    if args.check:
        committed = json.loads(CARD_PATH.read_text())
        skip = {"generated"}
        stale = [k for k in card if k not in skip and committed.get(k) != card[k]]
        if stale:
            print(f"stale model card sections: {', '.join(stale)} — re-run make_model_card and commit it",
                  file=sys.stderr)
            return 1
        print("model card matches the evidence")
        return 0
    CARD_PATH.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {CARD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
