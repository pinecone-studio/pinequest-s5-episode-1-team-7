"""Download the HMU-GC-HE-30K stomach dataset and convert it to engine/data/hmu-gc/ as HDF5 (issue #53).

HMU-GC-HE-30K (Lou et al., Sci Data 2025, figshare 10.6084/m9.figshare.25954813, CC BY 4.0):
224x224 H&E tiles from 300 gastric cancer slides (Aperio AT2, 20x objective, so ~0.5 µm/px,
the same scale as the colon data), 3,887 per class in 8 classes. Tumour (TUM, tumour
epithelium) is the positive class; fat, debris, lymphocytes, mucus, muscle, normal mucosa
and stroma are "no tumour".

The files are named <class>_<n>.png with no slide or patient ID. Neighbouring numbers look
alike for ~10-20 tiles (about one slide's share of a class: 3,887 / 300 = 13), so the tiles
are in slide order. A random split would put tiles of one slide in train and test, so each
class is split by number instead, with the same ranges for every class and a GAP-tile gap
at each boundary:
  train  1-2700    valid  2721-3290    test  3311-3887
Slides are not known for certain, so some leakage at the boundaries is still possible.

Writes PCam's layout (training/pcam.py): x (N, 224, 224, 3) uint8, y (N,) uint8, plus cls
(N,) uint8 (index into CLASSES) and idx (N,) the tile number. Each split is stored in a fixed
random order. 3.25 GB download (kept, MD5-checked), ~4.5 GB of HDF5.

    python -m training.download_hmu_gc
"""
import argparse
import hashlib
import zipfile
from pathlib import Path

import cv2
import h5py
import numpy as np

from training.download_nct_crc import shuffle_split, write_split
from training.download_pcam import download
from training.pcam import DATASETS, split_paths

ZIP_URL = "https://ndownloader.figshare.com/files/46765759"
ZIP_NAME = "HMU-GC-HE-30K.zip"
ZIP_MD5 = "0d55aa70ac70cb237402bc035bbd2355"
CLASSES = ("ADI", "DEB", "LYM", "MUC", "MUS", "NOR", "STR", "TUM")
PER_CLASS = 3887
TILE = 224
GAP = 20
RANGES = {"train": (1, 2700), "valid": (2700 + GAP + 1, 3290), "test": (3290 + GAP + 1, PER_CLASS)}


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_zip(data_dir: Path) -> Path:
    dest = data_dir / ZIP_NAME
    if dest.exists() and md5sum(dest) == ZIP_MD5:
        return dest
    download(ZIP_URL, dest)
    if md5sum(dest) != ZIP_MD5:
        dest.unlink()
        raise RuntimeError(f"MD5 mismatch for {ZIP_NAME}; deleted it, run again to re-download")
    return dest


def read_tile(archive: zipfile.ZipFile, name: str) -> np.ndarray:
    bgr = cv2.imdecode(np.frombuffer(archive.read(name), np.uint8), cv2.IMREAD_COLOR)
    if bgr is None or bgr.shape[:2] != (TILE, TILE):
        raise ValueError(f"unexpected image {name}: {None if bgr is None else bgr.shape}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def split_members(split: str) -> list:
    """[(class index, tile number)] of one split, by number range (see the module docstring)."""
    low, high = RANGES[split]
    return [(c, n) for c in range(len(CLASSES)) for n in range(low, high + 1)]


def convert_split(split: str, archive: zipfile.ZipFile, data_dir: Path) -> None:
    if all(p.exists() for p in split_paths(split, data_dir, "hmu_gc")):
        print(f"[{split}] already present")
        return
    print(f"[{split}]")
    members = split_members(split)

    def batches(size: int = 512):
        for start in range(0, len(members), size):
            part = members[start:start + size]
            images = np.stack([read_tile(archive, f"all_image/{CLASSES[c]}/{CLASSES[c]}_{n}.png") for c, n in part])
            yield images, np.array([c for c, _ in part], dtype=np.uint8)

    write_split(split, batches(), len(members), data_dir, "hmu_gc", CLASSES)
    with h5py.File(split_paths(split, data_dir, "hmu_gc")[1], "a") as fy:
        fy.create_dataset("idx", data=np.array([n for _, n in members], dtype=np.int32))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DATASETS["hmu_gc"]["dir"])
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(fetch_zip(args.data_dir)) as archive:
        for split in RANGES:
            convert_split(split, archive, args.data_dir)
    for split in RANGES:
        shuffle_split(split, args.data_dir, dataset="hmu_gc")
    print(f"Done: {args.data_dir}")


if __name__ == "__main__":
    main()
