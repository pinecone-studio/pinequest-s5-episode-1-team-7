"""Download the HMU-GC-HE-30K stomach dataset and convert it to engine/data/hmu-gc/ as HDF5.

HMU-GC-HE-30K (Lou et al. 2024, figshare 25954813, CC BY 4.0 — redistribution of
trained weights is allowed with attribution): ~31,000 tiles of 224x224 H&E at
~0.5 µm/px (Aperio AT2 scanner, 20x objective; 0.5 is the AT2's nominal 20x scale,
same as the colon data) in 8 tissue classes (a 9th folder, BACK, is tolerated if
present). Tumour (TUM, gastric adenocarcinoma)
is the positive class; every other class is "no tumour" (same mapping as colon).

Splits: file names carry no patient or slide IDs, so train/valid/test are a
stratified random 80/10/10 split (fixed seed). Tiles from one slide can land in
several splits, so treat the test score as slightly optimistic and re-check on
PLISM stomach (43_stomach normal vs 38_EBVGC, a single cancer subtype, so a sanity
check only) and on real captures.

~3 GB download, read straight from the zip (no extra disk space for extraction).

    python -m training.download_hmu_gc [--data-dir ...]

Only the standard library plus cv2/h5py/numpy are imported here, so the split
and label helpers stay unit-testable without the training environment.
"""
import argparse
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import cv2
import h5py
import numpy as np

ARTICLE_URL = "https://api.figshare.com/v2/articles/journal/25954813"
ARCHIVE = "HMU-GC-HE-30K.zip"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")

# Tissue classes, in the same order as the colon data where they overlap (the y
# file records these names, so keep them stable). BACK may be absent upstream.
CLASSES = ("ADI", "BACK", "DEB", "LYM", "MUC", "MUS", "NOR", "STR", "TUM")
TUMOUR = CLASSES.index("TUM")
TILE = 224
TRAIN_FRAC, VALID_FRAC = 0.8, 0.1
SEED = 0


def label_for_class(name: str) -> int:
    """Folder name -> class index. Raises ValueError for anything else."""
    try:
        return CLASSES.index(name.upper())
    except ValueError:
        raise ValueError(f"unknown HMU-GC tissue class {name!r}") from None


def collect_tiles(archive: Path) -> list:
    """[(member name, label)] of every class tile in the zip, sorted."""
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    tiles = []
    for name in names:
        parts = Path(name).parts
        if len(parts) < 2 or not name.lower().endswith(IMAGE_SUFFIXES):
            continue
        folder = parts[-2]
        try:
            label = label_for_class(folder)
        except ValueError:
            continue  # e.g. a preview image next to the class folders
        tiles.append((name, label))
    return sorted(tiles)


def decode(data: bytes) -> np.ndarray:
    """Image bytes -> RGB uint8 (224, 224, 3)."""
    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("undecodable image in archive")
    if bgr.shape[:2] != (TILE, TILE):
        raise ValueError(f"expected {TILE}x{TILE} tiles, got {bgr.shape[:2]}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def stratified_split(labels: np.ndarray, seed: int = SEED,
                     fractions: tuple = (TRAIN_FRAC, VALID_FRAC, 1 - TRAIN_FRAC - VALID_FRAC)
                     ) -> tuple:
    """Per-class shuffled (train, valid, test) index arrays. Raises ValueError
    when a class is too small to fill every split."""
    rng = np.random.default_rng(seed)
    out = ([], [], [])
    for c in np.unique(labels):
        idx = rng.permutation(np.flatnonzero(labels == c))
        cuts = np.cumsum([int(f * len(idx)) for f in fractions[:2]])
        if cuts[0] == 0 or cuts[1] - cuts[0] == 0 or len(idx) - cuts[1] == 0:
            raise ValueError(f"class {c} has only {len(idx)} tiles: cannot fill all splits")
        out[0].append(idx[:cuts[0]])
        out[1].append(idx[cuts[0]:cuts[1]])
        out[2].append(idx[cuts[1]:])
    return tuple(np.sort(np.concatenate(part)) for part in out)


def _dataset():
    from training.pcam import DATASETS
    return DATASETS["hmu_gc"]


def _split_paths(split: str, data_dir: Path):
    from training.pcam import split_paths
    return split_paths(split, data_dir, "hmu_gc")


def write_split(split: str, batches, n: int, data_dir: Path) -> None:
    """Write one split from an iterable of (images, classes) batches with n rows in total."""
    x_path, y_path = _split_paths(split, data_dir)
    x_tmp, y_tmp = (p.with_name(p.name + ".tmp") for p in (x_path, y_path))
    classes = np.zeros(n, dtype=np.uint8)
    i = 0
    with h5py.File(x_tmp, "w") as fx:
        # Contiguous and uncompressed, so training can memory-map it (see pcam.PCamBatches).
        x = fx.create_dataset("x", shape=(n, TILE, TILE, 3), dtype=np.uint8)
        for images, cls in batches:
            if i + len(cls) > n:
                raise RuntimeError(f"{split}: more than {n} images")
            x[i:i + len(cls)] = images
            classes[i:i + len(cls)] = cls
            i += len(cls)
    if i != n:
        x_tmp.unlink()
        raise RuntimeError(f"{split}: expected {n} images, got {i}")
    with h5py.File(y_tmp, "w") as fy:
        fy.create_dataset("y", data=(classes == TUMOUR).astype(np.uint8))
        fy.create_dataset("cls", data=classes)
        fy.attrs["classes"] = ",".join(CLASSES)
    x_tmp.replace(x_path)
    y_tmp.replace(y_path)
    print(f"  {split}: {n} tiles, {np.mean(classes == TUMOUR):.1%} tumour")


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_archive(data_dir: Path) -> Path:
    """Download HMU-GC-HE-30K.zip from figshare (skipped when present and intact)."""
    with urllib.request.urlopen(ARTICLE_URL) as response:
        article = json.load(response)
    files = [f for f in article["files"] if f["name"] == ARCHIVE]
    if not files:
        raise RuntimeError(f"{ARCHIVE} not found in figshare article 25954813")
    meta = files[0]
    dest = data_dir / ARCHIVE
    if dest.exists() and dest.stat().st_size == meta["size"] and _md5(dest) == meta.get("computedMd5", _md5(dest)):
        print(f"  {ARCHIVE} already present")
        return dest
    print(f"  downloading {ARCHIVE} ({meta['size'] / 1e9:.1f} GB)...", flush=True)
    urllib.request.urlretrieve(meta["download_url"], dest)
    if dest.stat().st_size != meta["size"]:
        dest.unlink()
        raise RuntimeError(f"{ARCHIVE}: expected {meta['size']} bytes, got {dest.stat().st_size}")
    return dest


def convert(data_dir: Path) -> None:
    if all(p.exists() for s in ("train", "valid", "test") for p in _split_paths(s, data_dir)):
        print("splits already present")
        return
    archive = fetch_archive(data_dir)
    tiles = collect_tiles(archive)
    if not tiles:
        raise RuntimeError(f"no class tiles found in {archive}")
    labels = np.array([label for _, label in tiles], dtype=np.uint8)
    present = sorted(set(labels.tolist()))
    print(f"  {len(tiles)} tiles in classes {[CLASSES[c] for c in present]}")
    parts = stratified_split(labels)
    with zipfile.ZipFile(archive) as zf:
        for split, idx in zip(("train", "valid", "test"), parts):
            batches = []
            for j in range(0, len(idx), 512):
                chunk = idx[j:j + 512]
                images = np.stack([decode(zf.read(tiles[k][0])) for k in chunk])
                batches.append((images, labels[chunk]))
            write_split(split, batches, len(idx), data_dir)


def shuffle_split(split: str, data_dir: Path, seed: int = SEED, chunk: int = 2048) -> None:
    """Rewrite a split in a fixed random order, once (marked in the y file).

    Tiles of one class sit together in the zip, so without this the first N tiles
    (--limit smoke runs, quick checks) would all be one tissue class.
    """
    from training.download_nct_crc import shuffle_split
    shuffle_split(split, data_dir, seed, chunk, dataset="hmu_gc")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    data_dir = args.data_dir or _dataset()["dir"]
    data_dir.mkdir(parents=True, exist_ok=True)
    convert(data_dir)
    for split in ("valid", "test", "train"):
        shuffle_split(split, data_dir)
    print(f"Done: {data_dir}")


if __name__ == "__main__":
    main()
