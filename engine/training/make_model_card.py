"""Generate the committed model card (engine/model/model_card.json).

The card is the evidence behind the frontend's "About the AI" page: every
number comes from a results file, the model file, or the pipeline constants,
and the generator FAILS when they disagree — so the card cannot drift from
the evidence. Re-run whenever the model, the thresholds, or any results file
changes, and commit the card with them::

    python -m training.make_model_card            # from engine/
    python -m training.make_model_card --check    # CI: exit 1 when the committed card is stale
    python -m training.make_model_card --organ colon   # engine/model/colon/model_card.json (issue #53)

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
TEACHER_RESULTS = "teacher_hibou-b.json"
SCORING_RESULTS = "slide_scoring.json"
PLISM_RESULTS = "plism_model_fp32_kd-hibou.json"
PLISM_DIRECT_RESULTS = "plism_model_fp32.json"
INT8_RESULTS = "int8_minmax_fp32convs10_pc_rr.json"
LITERATURE_RESULTS = "literature_pcam.json"  # published PCam baselines, quoted with their source

# PLISM image scale that matches the training magnification (issue #35).
PLISM_GOOD_SCALE = "0.6"


def _load(name: str) -> dict:
    with open(RESULTS / name, encoding="utf-8") as f:
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


LOCAL_BUDGET_S = 1.5  # TDD: under 1.5 s per slide on a clinic CPU; slower models still run, "slowly"


def _teacher_row(teacher: dict, shipped_s: float) -> dict:
    """Comparison row for the Hibou-B teacher: its accuracy, and its measured CPU speed and size."""
    seconds = teacher["cpu"]["cpu_seconds_per_slide"]
    slower = round(seconds / shipped_s, -1)
    return {"model": "Hibou-B pathology foundation model (the teacher)", "test_auc": round(teacher["test_auc"], 4),
            "size_mb": teacher["cpu"]["size_mb"], "per_slide_s": seconds,
            "local": "yes" if seconds <= LOCAL_BUDGET_S else "slow",
            "note": f"most accurate, but about {slower:.0f}x slower than this model on a CPU"}


def build_card() -> dict:
    main = _load(MAIN_RESULTS)
    teacher = _load(TEACHER_RESULTS)
    scoring = _load(SCORING_RESULTS)
    plism = _load(PLISM_RESULTS)
    int8 = _load(INT8_RESULTS)
    literature = _load(LITERATURE_RESULTS)
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
        # Only completely different models: variants of the same network (without the teacher,
        # INT8) are covered in engine/README.md, not on the About page.
        "comparison": [
            {"model": "This model: MobileNetV3-Small, distilled from Hibou-B",
             "test_auc": round(test["auc"], 4), "size_mb": round(size_bytes / 1e6, 2),
             "per_slide_s": int8["fp32"]["seconds_per_slide"], "local": "yes", "note": "shipped"},
            _teacher_row(teacher, int8["fp32"]["seconds_per_slide"]),
            *[{"model": b["model"], "test_auc": b["test_auc"], "size_mb": round(b["params"] * 4 / 1e6, 1),
               "per_slide_s": b["per_slide_s"], "per_slide_range_s": b["per_slide_range_s"], "speed_estimated": True,
               "local": b["local"], "note": "published accuracy; speed estimated"}
              for b in literature["baselines"]],
        ],
        "literature": {
            "note": literature["note"],
            "source": literature["source"],
            "url": literature["url"],
            "baselines": literature["baselines"],
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


# Other organs' models (issue #53): the evidence files for each, and its PLISM tissues.
# Same card layout as lymph node, so the About page can show any organ's card.
ORGAN_CARDS = {
    "colon": {
        "name": "Colon MobileNetV3-Small, Hibou-B-distilled",
        "trained_on": "colorectal tissue: tumour epithelium vs 8 non-tumour classes (NCT-CRC-HE-100K)",
        "test_split": "CRC-VAL-HE-7K test half",
        "main": "colon_mobilenet_v3_small_224_kd-hibou.json",
        "teacher": "teacher_hibou-b_nct_crc.json",
        "scoring": "slide_scoring_colon.json",
        "plism": "plism_colon_model_fp32.json",
        "plism_scale": "0.5",  # PLISM ~0.25 µm/px -> the model's 0.5 µm/px
        "plism_tissues": "normal right colon vs colon adenocarcinoma + metastatic colorectal cancer",
    },
}


def build_organ_card(organ: str) -> dict:
    """Card for another organ's model, from its own evidence files (same layout as build_card)."""
    spec_files = ORGAN_CARDS[organ]
    sys.path.insert(0, str(ENGINE_ROOT))
    from pipeline.inference import PREFERRED_PROVIDERS
    from pipeline.organs import get_organ
    from pipeline.scoring import TEMPERATURE

    spec = get_organ(organ)
    main = _load(spec_files["main"])
    teacher = _load(spec_files["teacher"])
    scoring = _load(spec_files["scoring"])
    plism = _load(spec_files["plism"])
    int8 = _load(INT8_RESULTS)
    model_path = spec.model_path
    if not model_path.is_file():
        raise SystemExit(f"{organ} model missing: {model_path}")
    facts = _onnx_facts(model_path)

    meta = facts["metadata"]
    assert abs(float(meta["test_auc"]) - round(main["test"]["auc"], 4)) < 1e-9, \
        f"ONNX test_auc {meta['test_auc']} != {spec_files['main']} test.auc {main['test']['auc']:.4f}"
    assert meta.get("organ") == organ == main.get("organ"), f"ONNX / results organ is not {organ}"
    assert meta.get("distilled_from") == main.get("teacher")
    assert meta.get("input_size") == str(main["config"]["img_size"])
    chosen = scoring["chosen"]
    assert scoring.get("organ") == organ and scoring.get("model") == model_path.name
    assert (spec.w_max, spec.top_k) == (chosen["w_max"], chosen["top_k"]), f"{organ}: scoring formula != tuned choice"
    assert (round(chosen["red"], 2), round(chosen["yellow"], 2)) == (spec.red, spec.yellow), \
        f"{organ}: thresholds in pipeline/organs.py != tuned choice"
    assert plism.get("organ") == organ

    test = main["test"]
    at90 = main["evaluation"]["tta1"]["test_at_val_90_sensitivity"]
    size_bytes = model_path.stat().st_size
    by_device = plism["by_scale"][spec_files["plism_scale"]]
    scanners = {d: round(r["organ"]["normal_false_alarm"], 4) for d, r in by_device.items() if r["kind"] == "scanner"}
    phones = {d: round(r["organ"]["normal_false_alarm"], 4) for d, r in by_device.items() if r["kind"] == "phone"}
    phone_auc = [r["organ"]["cancer_vs_normal_auc"] for r in by_device.values() if r["kind"] == "phone"]
    phone_flagged = [r["organ"]["cancer_flagged"] for r in by_device.values() if r["kind"] == "phone"]
    other_fa = [round(r["normal_tissue_false_alarm"], 4) for r in by_device.values() if r["kind"] == "phone"]
    slide_test = scoring["test"]
    fractions = {frac: {"auc": round(slide_test[frac]["auc"], 4), "red": slide_test[frac]["red"],
                        "yellow_or_red": slide_test[frac]["yellow_or_red"]}
                 for frac in ("tumour_1pct", "tumour_2pct", "tumour_5pct", "tumour_10pct", "tumour_25pct")}
    try:
        tuned_commit = subprocess.run(
            ["git", "-C", str(ENGINE_ROOT.parent), "log", "-1", "--format=%H", "--", str(RESULTS / spec_files["scoring"])],
            capture_output=True, text=True, check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        tuned_commit = None

    teacher_cpu = _load(TEACHER_RESULTS)["cpu"]  # the same frozen Hibou-B backbone for every organ
    # Only completely different models: variants of the same network (without the teacher, INT8)
    # are covered in engine/README.md, not on the About page.
    comparison = [
        {"model": "This model: MobileNetV3-Small, distilled from Hibou-B", "test_auc": round(test["auc"], 4),
         "size_mb": round(size_bytes / 1e6, 2), "per_slide_s": int8["fp32"]["seconds_per_slide"],
         "local": "yes", "note": "shipped"},
        _teacher_row({**teacher, "cpu": teacher_cpu}, int8["fp32"]["seconds_per_slide"]),
    ]

    return {
        "name": spec_files["name"],
        "version": f"{organ}/{model_path.name}",
        "organ": organ,
        "file": {
            "name": model_path.name,
            "sha256": _sha256(model_path),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1e6, 2),
            "committed": _git_date(model_path),
        },
        "architecture": {
            "name": "MobileNetV3-Small",
            "params": facts["params"],
            "input_px": main["config"]["img_size"],
            "input_scale_um_per_px": spec.um_per_px,
        },
        "provenance": {
            "dataset": main["dataset"],
            "backbone": "ImageNet-pretrained MobileNetV3-Small",
            "training": f"fine-tuned on {spec_files['trained_on']} ({main['config']['epochs']} epochs, best epoch "
                        f"{main['best_epoch']}, strong augmentation + EMA, {main['config']['batch_size']}-batch)",
            "distilled_from": f"{main['teacher']} (foundation model, histai/hibou-b; its own head trained on this dataset)",
            "date_trained": _git_date(RESULTS / spec_files["main"]),
            "export_metadata": {k: meta[k] for k in ("arch", "dataset", "organ", "val_auc", "test_auc", "test_accuracy",
                                                     "distilled_from") if k in meta},
        },
        "runtime": {
            "offline": True,
            "runs_on": "this clinic PC only: no cloud, no data leaves the clinic (TDD 1.2, 7.1)",
            "providers_preference": list(PREFERRED_PROVIDERS),
            "measured_per_slide_s": {
                "value": int8["fp32"]["seconds_per_slide"],
                "context": "median warmed run, 150 patches, batch 16, 4 threads, i5-13400F "
                           f"({int8['benchmark']}). Same-graph reference: every organ's model is the "
                           "same MobileNetV3-Small graph as the measured lymph-node model.",
            },
        },
        "patch_metrics": {
            "split": f"{spec_files['test_split']} (n={test['n']:,})",
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
            "formula": f"sigmoid(mean(top-{spec.top_k} patch log-odds) / {TEMPERATURE:g})",
            "thresholds": {"red": spec.red, "yellow": spec.yellow},
            "tuned": _git_date(RESULTS / spec_files["scoring"]),
            "tuned_commit": tuned_commit,
            "normal_slides": {"red": slide_test["normal_slides"]["red"],
                              "yellow_or_red": slide_test["normal_slides"]["yellow_or_red"]},
            "tumour_fractions": fractions,
        },
        "plism": {
            "at": f"{spec_files['plism_scale']}x (≈{spec.um_per_px} µm/px, the training magnification, issue #35)",
            "source": spec_files["plism"],
            "metric": f"share of normal {organ.replace('_', ' ')} patches flagged (P ≥ 0.5)",
            "scanners": scanners,
            "phones": phones,
            "organ_cancer_on_phones": {"tissues": spec_files["plism_tissues"],
                                       "flagged_min": round(min(phone_flagged), 4), "flagged_max": round(max(phone_flagged), 4),
                                       "auc_min": round(min(phone_auc), 4), "auc_max": round(max(phone_auc), 4)},
            "other_tissues_false_alarm": {"min": min(other_fa), "max": max(other_fa),
                                          "note": f"normal tissue of all organs on phones: only valid for {organ}"},
        },
        "comparison": comparison,
        "literature": {
            "note": "Published baselines were not recorded with these runs, so none are quoted: "
                    "numbers here come only from the evidence files above.",
            "baselines": [],
        },
        "limitations": [
            f"Trained only on {organ.replace('_', ' ')} tissue. Use it only for {organ.replace('_', ' ')} slides: normal tissue "
            f"of all PLISM organs was flagged {min(other_fa):.0%}–{max(other_fa):.0%} on phones.",
            f"Needs a calibrated magnification (issue #35): photos are resized to {spec.um_per_px} µm/px.",
            "The test half shares patients with the validation half used for the epoch and threshold choices "
            "(CRC-VAL-HE-7K has no patient IDs), and its tiles are stain-normalised, unlike training.",
            "Slide thresholds were tuned on slides simulated from validation tiles; re-tune on real captures.",
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
    parser = argparse.ArgumentParser(description="Generate an organ model's model_card.json from the evidence files.")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when the committed card differs (ignoring the generation stamp)")
    parser.add_argument("--organ", default="lymph_node", choices=["lymph_node", *ORGAN_CARDS])
    args = parser.parse_args(argv)
    if args.organ == "lymph_node":
        card, card_path = build_card(), CARD_PATH
    else:
        sys.path.insert(0, str(ENGINE_ROOT))
        from pipeline.organs import get_organ
        card, card_path = build_organ_card(args.organ), get_organ(args.organ).card_path
    if args.check:
        committed = json.loads(card_path.read_text(encoding="utf-8"))
        skip = {"generated"}
        stale = [k for k in card if k not in skip and committed.get(k) != card[k]]
        if stale:
            print(f"stale model card sections: {', '.join(stale)} — re-run make_model_card and commit it",
                  file=sys.stderr)
            return 1
        print("model card matches the evidence")
        return 0
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {card_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
