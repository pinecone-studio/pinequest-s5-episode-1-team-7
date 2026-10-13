"""How does the patch classifier hold up on smartphone captures? Evaluation on PLISM-sm.

PLISM (Ochi et al., Sci Data 2024, CC BY 4.0): the same tissue-microarray spots (46 tissues,
13 H&E stain conditions) imaged by 7 slide scanners and 6 smartphones on a microscope
eyepiece, registered so every device shows the same field. Images are 512 x 512 at about
0.45 um/px, close to the model's training scale (PCam 96 px upsampled to 224, ~0.42 um/px),
so the centre 448 x 448 is scored as four native 224 px patches (fewer at --scales < 1).

Reported per device:
  - normal lymph node: share of patches with P >= 0.5 (false alarms; PCam's own normal tissue)
  - malignant vs normal tissue AUC: rough, because these cancers are not breast metastases
  - agreement with the reference scanner on the same spot: mean |dP| and P >= 0.5 flips
  - sharpness (Laplacian variance, as the backend's blur gate)

Labels are per tissue type only, so treat the numbers as a domain-shift check, not accuracy.

Download (19 GB, Figshare+ article 23590791) and extract, e.g. on B:
    curl -L -o PLISM_sm.tar.gz https://ndownloader.figshare.com/files/41397708
    curl -L -o PLISM_sm_en.csv https://ndownloader.figshare.com/files/41397675
    tar -xzf PLISM_sm.tar.gz
then, from engine/:
    python -m training.plism_eval --root B:/pinequest-data/plism/PLISM_sm --csv B:/pinequest-data/plism/PLISM_sm_en.csv
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from sklearn.metrics import roc_auc_score

from pipeline.inference import DEFAULT_MODEL_PATH, PatchClassifier

RESULTS_PATH = Path(__file__).resolve().parents[1] / "training" / "results" / "plism_eval.json"
SCANNERS = ("GT450", "AT2", "S360", "S60", "S210", "SQ", "P")
PHONES = ("galaxy", "iphone13", "iphone6", "itel", "moto", "redmi")
REFERENCE = "GT450"
NORMAL_LYMPH_NODE = "12_lymph_node"
# Malignant tumours; benign/borderline ones (30_myxofibroma, 35_thymoma) are left out of the AUC.
MALIGNANT = {"31_NEC", "32_ESCC", "33_RCCC", "34_colon_adenocarcionma", "36_GIST",
             "37_metastatic_colorectal_cancer", "38_EBVGC", "39_HCC", "41_dedifferentiated_liposarcoma"}
EXCLUDED = {"30_myxofibroma", "35_thymoma"}
PATCH = 224


def centre_patches(image: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """The largest centred n x n grid of 224 px RGB patches (n = 2 at native scale)."""
    if scale != 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    h, w = image.shape[:2]
    n = min(h, w) // PATCH
    if n == 0:
        raise ValueError(f"image smaller than one {PATCH} px patch: {image.shape}")
    top, left = (h - n * PATCH) // 2, (w - n * PATCH) // 2
    centre = image[top:top + n * PATCH, left:left + n * PATCH]
    return centre.reshape(n, PATCH, n, PATCH, 3).swapaxes(1, 2).reshape(n * n, PATCH, PATCH, 3)


def sharpness(image: np.ndarray) -> float:
    return float(cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var())


def score_all(rows, root: Path, classifier: PatchClassifier, scale: float) -> dict:
    """{(stain, device, coordinate): (4 patch probabilities, sharpness)}."""
    out = {}
    for i, row in enumerate(rows):
        bgr = cv2.imread(str(root / row["path"].lstrip("/")))
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        out[(row["stain"], row["device"], row["coordinate"])] = (classifier.predict(centre_patches(rgb, scale)), sharpness(rgb))
        if (i + 1) % 2000 == 0:
            print(f"\r  scored {i + 1}/{len(rows)}", end="", flush=True)
    print()
    return out


def summarise(rows, scores: dict) -> dict:
    tissue = {(r["stain"], r["device"], r["coordinate"]): r["tissue_type"] for r in rows}
    per_device = defaultdict(lambda: {"lymph": [], "malig": [], "normal": [], "sharp": []})
    for key, (probs, sharp) in scores.items():
        d, t = per_device[key[1]], tissue[key]
        d["sharp"].append(sharp)
        if t == NORMAL_LYMPH_NODE:
            d["lymph"].extend(probs)
        if t in MALIGNANT:
            d["malig"].extend(probs)
        elif t not in EXCLUDED:
            d["normal"].extend(probs)

    report = {}
    for device in (*SCANNERS, *PHONES):
        if device not in per_device:
            continue
        d = per_device[device]
        lymph, malig, normal = map(np.asarray, (d["lymph"], d["malig"], d["normal"]))
        entry = {
            "kind": "scanner" if device in SCANNERS else "phone",
            "lymph_node_false_alarm": float(np.mean(lymph >= 0.5)) if len(lymph) else None,
            "lymph_node_mean_p": float(lymph.mean()) if len(lymph) else None,
            "malignant_vs_normal_auc": float(roc_auc_score(np.r_[np.zeros(len(normal)), np.ones(len(malig))], np.r_[normal, malig]))
            if len(malig) and len(normal) else None,
            "normal_tissue_false_alarm": float(np.mean(normal >= 0.5)) if len(normal) else None,
            "sharpness_median": float(np.median(d["sharp"])),
            "sharpness_p05": float(np.quantile(d["sharp"], 0.05)),
        }
        # Agreement with the reference scanner on the same spot and stain.
        diffs, flips = [], []
        for (stain, dev, coord), (probs, _) in scores.items():
            ref = scores.get((stain, REFERENCE, coord))
            if dev == device and ref is not None and device != REFERENCE:
                diffs.append(np.abs(probs - ref[0]).mean())
                flips.append(np.mean((probs >= 0.5) != (ref[0] >= 0.5)))
        if diffs:
            entry["vs_reference_mean_abs_dp"] = float(np.mean(diffs))
            entry["vs_reference_flip_rate"] = float(np.mean(flips))
        entry["images"] = len(d["sharp"])
        report[device] = entry
    return report


def print_table(report: dict, title: str) -> None:
    print(f"\n{title}")
    print(f"{'device':9s} {'kind':7s} {'LN false':>9s} {'normal FA':>9s} {'malig AUC':>9s} {'|dP| ref':>9s} {'flips':>6s} {'sharp med':>9s} {'sharp p5':>8s}")
    for device, e in report.items():
        fmt = lambda v, f: (f % v) if v is not None else "-"
        print(f"{device:9s} {e['kind']:7s} {fmt(e['lymph_node_false_alarm'], '%9.3f')} {fmt(e['normal_tissue_false_alarm'], '%9.3f')} "
              f"{fmt(e['malignant_vs_normal_auc'], '%9.3f')} {fmt(e.get('vs_reference_mean_abs_dp'), '%9.3f')} "
              f"{fmt(e.get('vs_reference_flip_rate'), '%6.3f')} {e['sharpness_median']:9.0f} {e['sharpness_p05']:8.0f}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, required=True, help="extracted PLISM_sm folder (contains <stain>/<device>/*.png)")
    p.add_argument("--csv", type=Path, required=True, help="PLISM_sm_en.csv")
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    p.add_argument("--scales", type=float, nargs="+", default=[1.0], help="image rescale factors to test (1.0 = native)")
    p.add_argument("--limit", type=int, default=0, help="only the first N spots per device (quick check)")
    args = p.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    if args.limit:
        keep = {c for c in sorted({r["coordinate"] for r in rows})[: args.limit]}
        rows = [r for r in rows if r["coordinate"] in keep]
    classifier = PatchClassifier(args.model, batch_size=64)

    results = {"model": args.model.name, "reference_scanner": REFERENCE, "by_scale": {}}
    for scale in args.scales:
        print(f"scale {scale}: scoring {len(rows)} images")
        report = summarise(rows, score_all(rows, args.root, classifier, scale))
        results["by_scale"][str(scale)] = report
        print_table(report, f"PLISM-sm, scale {scale} (LN = normal lymph node, FA = P >= 0.5, |dP| and flips vs {REFERENCE})")

    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nresults: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
