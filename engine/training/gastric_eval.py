"""Does the stomach model see the gastric cancer types it was not trained on? (issue #53)

HMU-GC-HE-30K (the stomach training data) is mostly gland-forming adenocarcinoma, and PLISM's
only gastric cancer is EBV-associated, so neither can test diffuse or signet-ring cancer.
This scores whole slides from two open archives instead, through the NCI Imaging Data
Commons (IDC, public AWS bucket, no account):

  cancer  TCGA-STAD diagnostic slides (IDC collection tcga_stad, CC BY 3.0); histological
          type from the GDC clinical data: signet ring cell carcinoma, diffuse type, and
          intestinal type for comparison
  normal  GTEx normal stomach (IDC collection gtex, CC BY 4.0), from organ donors; only
          slides whose pathology notes call the mucosa well preserved (many GTEx samples
          are autolysed). GTEx uses PAXgene fixation, TCGA formalin, so stain differs a bit

Each slide is downloaded, scored and deleted (they are 0.3-2 GB each). From the tissue mask,
up to FIELDS random "phone fields" are taken: FIELD x FIELD tiles of 224 px at 0.5 µm/px
(~1.3 mm, about one capture), and each is scored like the app does: tissue tiles only,
then the organ's slide score and red / yellow flag (pipeline/organs.py).

Every TCGA slide contains cancer, but not every field does, so field flag rates on TCGA
are a lower bound on sensitivity. The fair comparison is per slide: the highest field score
of a cancer slide against that of a normal GTEx slide (AUC per cancer type).

    python -m training.gastric_eval                 # ~80 TCGA + ~30 GTEx slides, ~7 h at ~3 MB/s
    python -m training.gastric_eval --limit 4       # quick check
Per-slide tile scores: data/gastric-eval/<slide>.npz; summary: training/results/gastric_eval.json
"""
import argparse
import concurrent.futures
import glob
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from sklearn.metrics import roc_auc_score

ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))
from pipeline.inference import PatchClassifier  # noqa: E402
from pipeline.masking import MIN_TISSUE_FRACTION, tissue_mask  # noqa: E402
from pipeline.organs import get_organ  # noqa: E402
from pipeline.scoring import risk_flag, slide_score  # noqa: E402

OUT_DIR = ENGINE_DIR / "data" / "gastric-eval"
RESULTS_PATH = ENGINE_DIR / "training" / "results" / "gastric_eval.json"
GDC_FILES = "https://api.gdc.cancer.gov/files"
GTEX_HISTOLOGY = "https://gtexportal.org/api/v2/histology/image"
TILE, UM_PER_PX = 224, 0.5
FIELD, FIELDS = 12, 20
MODELS = ("stomach", "colon")
GROUPS = {  # group -> (GDC primary_diagnosis, slides to take; 0 = all)
    "signet_ring": ("Signet ring cell carcinoma", 0),
    "diffuse": ("Carcinoma, diffuse type", 40),
    "intestinal": ("Adenocarcinoma, intestinal type", 25),
}
GTEX_SLIDES = 30
WELL_PRESERVED = re.compile(r"well[\s-]*preserved|excellent preservation")
NO_MUCOSA = re.compile(r"autoly|slough|denuded|no mucosa|muscularis only|all muscle")
SEED = 0


def gdc_diagnoses() -> dict:
    """{TCGA patient ID: primary_diagnosis} for TCGA-STAD diagnostic slides."""
    filters = {"op": "and", "content": [
        {"op": "=", "content": {"field": "cases.project.project_id", "value": "TCGA-STAD"}},
        {"op": "=", "content": {"field": "experimental_strategy", "value": "Diagnostic Slide"}},
    ]}
    query = urllib.parse.urlencode({"filters": json.dumps(filters), "size": 2000, "format": "json",
                                    "fields": "cases.submitter_id,cases.diagnoses.primary_diagnosis"})
    with urllib.request.urlopen(f"{GDC_FILES}?{query}") as response:
        hits = json.load(response)["data"]["hits"]
    return {h["cases"][0]["submitter_id"]: h["cases"][0]["diagnoses"][0].get("primary_diagnosis") for h in hits}


def gtex_well_preserved() -> set:
    """GTEx donors whose stomach slide's pathology notes call the mucosa well preserved.

    Donor IDs, because the portal's image IDs and IDC's container IDs differ in the last digit;
    each donor has one stomach slide.
    """
    ids, page = set(), 0
    while True:
        query = urllib.parse.urlencode({"tissueSiteDetail": "Stomach", "itemsPerPage": 10000, "page": page})
        with urllib.request.urlopen(f"{GTEX_HISTOLOGY}?{query}") as response:
            data = json.load(response)
        for row in data["data"]:
            notes = (row.get("pathologyNotes") or "").lower()
            if row["tissueSiteDetail"] == "Stomach" and WELL_PRESERVED.search(notes) and not NO_MUCOSA.search(notes):
                ids.add(row["subjectId"])
        page += 1
        if page >= data["paging_info"]["numberOfPages"]:
            return ids


def build_manifest(client) -> list:
    """[{slide, group, series, size_mb}]: one diagnostic slide per patient, a fixed random choice."""
    client.fetch_index("sm_index")
    rows = client.sql_query(
        "SELECT i.SeriesInstanceUID series, s.ContainerIdentifier slide, i.PatientID patient, i.collection_id, "
        "i.series_size_MB size_mb, s.primaryAnatomicStructure_CodeMeaning site "
        "FROM index i JOIN sm_index s USING (SeriesInstanceUID) WHERE i.collection_id IN ('tcga_stad', 'gtex')"
    )
    rng = np.random.default_rng(SEED)
    diagnoses = gdc_diagnoses()
    tcga = rows[(rows.collection_id == "tcga_stad") & rows.slide.str.contains("-DX")].sort_values("slide")
    tcga = tcga.drop_duplicates("patient")
    manifest = []
    for group, (diagnosis, n) in GROUPS.items():
        pick = tcga[tcga.patient.map(diagnoses) == diagnosis]
        if n and len(pick) > n:
            pick = pick.iloc[np.sort(rng.choice(len(pick), n, replace=False))]
        manifest += [{"slide": r.slide, "group": group, "series": r.series, "size_mb": round(r.size_mb)} for r in pick.itertuples()]
    keep = gtex_well_preserved()
    gtex = rows[(rows.collection_id == "gtex") & (rows.site == "Stomach") & rows.patient.isin(keep)]
    gtex = gtex.sort_values("slide").drop_duplicates("patient")
    if len(gtex) > GTEX_SLIDES:
        gtex = gtex.iloc[np.sort(rng.choice(len(gtex), GTEX_SLIDES, replace=False))]
    manifest += [{"slide": r.slide, "group": "gtex_normal", "series": r.series, "size_mb": round(r.size_mb)} for r in gtex.itertuples()]
    return manifest


def fetch(client, item: dict, tmp: Path) -> Path:
    """Download one slide series; returns the folder of its DICOM files."""
    target = tmp / item["slide"]
    if not target.exists():
        part = tmp / (item["slide"] + ".part")
        shutil.rmtree(part, ignore_errors=True)
        client.download_from_selection(seriesInstanceUID=[item["series"]], downloadDir=str(part), quiet=True)
        part.rename(target)
    return Path(max(glob.glob(str(target / "**" / "*.dcm"), recursive=True), key=os.path.getsize)).parent


def phone_fields(folder: Path, rng) -> list:
    """Up to FIELDS fields of FIELD x FIELD tiles (uint8, TILE px at UM_PER_PX) with their tissue fractions.

    wsidicom rather than openslide: about half the TCGA slides are JPEG 2000, which openslide's
    DICOM reader does not decode.
    """
    from wsidicom import WsiDicom

    slide = WsiDicom.open(str(folder))
    base, low = slide.levels[0], slide.levels[-1]
    mpp = float(base.pixel_spacing.width) * 1000  # mm -> µm
    down = base.size.width / low.size.width
    thumb = np.asarray(slide.read_region((0, 0), low.level, (low.size.width, low.size.height)).convert("RGB"))
    mask = tissue_mask(thumb)
    src = TILE * UM_PER_PX / mpp           # tile size in level-0 pixels
    span = FIELD * src                     # field size in level-0 pixels
    m = max(1, int(round(span / down)))    # field size in mask pixels
    # Field top-left corners (mask pixels) where at least half the field is tissue.
    integral = cv2.integral(mask.astype(np.uint8))
    h, w = mask.shape
    ys, xs = np.mgrid[0:max(1, h - m):max(1, m // 4), 0:max(1, w - m):max(1, m // 4)]
    ys, xs = ys.ravel(), xs.ravel()
    area = integral[ys + m, xs + m] - integral[ys, xs + m] - integral[ys + m, xs] + integral[ys, xs]
    good = np.flatnonzero(area >= 0.5 * m * m)
    fields = []
    for k in rng.permutation(good)[:FIELDS]:
        x0, y0 = xs[k] * down, ys[k] * down
        region = slide.read_region((int(x0), int(y0)), base.level, (int(round(span)), int(round(span)))).convert("RGB")
        field = cv2.resize(np.asarray(region), (FIELD * TILE, FIELD * TILE), interpolation=cv2.INTER_AREA)
        tiles = field.reshape(FIELD, TILE, FIELD, TILE, 3).swapaxes(1, 2).reshape(-1, TILE, TILE, 3)
        tissue = tissue_mask(field).reshape(FIELD, TILE, FIELD, TILE).mean(axis=(1, 3)).reshape(-1)
        fields.append((tiles, tissue))
    slide.close()
    return fields


def score_slide(folder: Path, classifiers: dict, rng) -> dict:
    """{model: (fields, tiles) P_malignant, NaN for non-tissue tiles} for one slide."""
    out = {name: [] for name in classifiers}
    for tiles, tissue in phone_fields(folder, rng):
        keep = tissue >= MIN_TISSUE_FRACTION
        for name, clf in classifiers.items():
            p = np.full(len(tiles), np.nan, dtype=np.float32)
            if keep.any():
                p[keep] = clf.predict(tiles[keep])
            out[name].append(p)
    return {name: np.array(v, dtype=np.float32).reshape(-1, FIELD * FIELD) for name, v in out.items()}


def field_scores(probs: np.ndarray, organ: str) -> np.ndarray:
    spec = get_organ(organ)
    return np.array([slide_score(p[~np.isnan(p)], spec.w_max, spec.top_k) for p in probs])


def summarise(manifest: list) -> dict:
    """Per model and group: field flag rates and tile share flagged; slide AUC of each cancer type vs normal."""
    report = {}
    for organ in MODELS:
        spec = get_organ(organ)
        per_group, best = {}, {}
        for item in manifest:
            npz = OUT_DIR / f"{item['slide']}.npz"
            if not npz.exists():
                continue
            probs = np.load(npz)[organ]
            if not len(probs):
                continue
            scores = field_scores(probs, organ)
            flags = [risk_flag(s, spec.red, spec.yellow) for s in scores]
            g = per_group.setdefault(item["group"], {"slides": 0, "fields": 0, "red": 0, "yellow_or_red": 0, "tiles": [], "best": []})
            g["slides"] += 1
            g["fields"] += len(scores)
            g["red"] += flags.count("red")
            g["yellow_or_red"] += flags.count("red") + flags.count("yellow")
            g["tiles"].append(probs[~np.isnan(probs)])
            g["best"].append(float(scores.max()))
            g.setdefault("slides_red", 0)
            g["slides_red"] += any(f == "red" for f in flags)
        rows = {}
        for group, g in per_group.items():
            tiles = np.concatenate(g["tiles"])
            rows[group] = {
                "slides": g["slides"], "fields": g["fields"],
                "fields_red": g["red"] / g["fields"], "fields_yellow_or_red": g["yellow_or_red"] / g["fields"],
                "slides_with_a_red_field": g["slides_red"] / g["slides"],
                "tiles_flagged": float(np.mean(tiles >= 0.5)), "tiles": int(len(tiles)),
            }
            best[group] = g["best"]
        normal = best.get("gtex_normal", [])
        for group in GROUPS:
            if group in best and normal:
                y = np.r_[np.zeros(len(normal)), np.ones(len(best[group]))]
                rows[group]["slide_auc_vs_gtex_normal"] = float(roc_auc_score(y, np.r_[normal, best[group]]))
        report[organ] = rows
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limit", type=int, default=0, help="only the first N slides of each group (quick check)")
    p.add_argument("--keep", action="store_true", help="keep the downloaded slides")
    args = p.parse_args()

    from idc_index import IDCClient

    client = IDCClient()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = build_manifest(client)
        manifest_path.write_text(json.dumps(manifest, indent=1))
    if args.limit:
        manifest = [m for g in ("signet_ring", "diffuse", "intestinal", "gtex_normal")
                    for m in [x for x in manifest if x["group"] == g][: args.limit]]
    todo = [m for m in manifest if not (OUT_DIR / f"{m['slide']}.npz").exists()]
    print({g: sum(m["group"] == g for m in manifest) for g in ("signet_ring", "diffuse", "intestinal", "gtex_normal")},
          f"{len(todo)} to score, {sum(m['size_mb'] for m in todo) / 1024:.0f} GB to download", flush=True)

    classifiers = {name: PatchClassifier(get_organ(name).model_path, batch_size=64) for name in MODELS}
    tmp = OUT_DIR / "tmp"
    tmp.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(1) as pool:  # download the next slide while scoring this one
        future = pool.submit(fetch, client, todo[0], tmp) if todo else None
        for i, item in enumerate(todo):
            path = future.result()
            future = pool.submit(fetch, client, todo[i + 1], tmp) if i + 1 < len(todo) else None
            rng = np.random.default_rng([SEED, i])
            try:
                result = score_slide(Path(path), classifiers, rng)
                np.savez_compressed(OUT_DIR / f"{item['slide']}.npz", **result)
                n = len(result[MODELS[0]])
                print(f"[{i + 1}/{len(todo)}] {item['group']:12s} {item['slide']}: {n} fields, "
                      f"stomach best field {field_scores(result['stomach'], 'stomach').max() if n else float('nan'):.3f}", flush=True)
            except Exception as exc:  # one unreadable slide shouldn't stop an overnight run
                print(f"[{i + 1}/{len(todo)}] {item['slide']}: FAILED {exc!r}", flush=True)
            if not args.keep:
                shutil.rmtree(tmp / item["slide"], ignore_errors=True)

    report = {"manifest": len(manifest), "field": f"{FIELD}x{FIELD} tiles of {TILE} px at {UM_PER_PX} µm/px, up to {FIELDS} per slide",
              "by_model": summarise(manifest)}
    if not args.limit:
        RESULTS_PATH.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["by_model"], indent=1))


if __name__ == "__main__":
    main()
