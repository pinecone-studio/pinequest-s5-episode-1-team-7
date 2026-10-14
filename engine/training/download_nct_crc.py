"""Download the NCT-CRC-HE colon dataset and convert it to engine/data/nct-crc/ as HDF5 (issue #53).

NCT-CRC-HE-100K (Kather et al. 2018, Zenodo 1214456, CC BY 4.0): 224x224 H&E tiles at
0.5 µm/px from 86 colorectal cancer slides, in 9 tissue classes. Tumour (TUM, colorectal
adenocarcinoma epithelium) is the positive class; every other class (fat, background,
debris, lymphocytes, mucus, smooth muscle, normal mucosa, stroma) is "no tumour".

  train  NCT-CRC-HE-100K-NONORM, 100,000 tiles. The non-normalised version, because phone
         captures are not stain-normalised either
  valid  half of CRC-VAL-HE-7K (7,180 tiles from 50 other patients), stratified by class
  test   the other half

The 7K set has no patient IDs, so valid and test share patients: test is independent of
training, but not of the epoch and threshold choices made on valid. Its tiles are
Macenko-normalised, unlike train.

Zenodo is slow, so this pulls the Hugging Face mirror (1aurent/NCT-CRC-HE, pinned revision),
checks each shard's SHA-256 and writes PCam's layout (see training/pcam.py): x (N, 224, 224, 3)
uint8, y (N,) uint8 tumour label, plus cls (N,) uint8 with the 9-class label in the y file.
Each split is then stored in a fixed random order (the sources are sorted by class). Parquet
shards are deleted once converted. ~14 GB download, ~16 GB of HDF5 (plus 15 GB free space
while train is reordered).

    python -m training.download_nct_crc
"""
import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import h5py
import numpy as np
import pyarrow.parquet as pq

from training.download_pcam import download, sha256sum
from training.pcam import DATASETS, split_paths

REPO = "1aurent/NCT-CRC-HE"
REVISION = "97765ecb14bf11ce7bb8779a1097d187844a67cb"
TREE_URL = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}/data"
FILE_URL = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{{path}}"
CLASSES = ("ADI", "BACK", "DEB", "LYM", "MUC", "MUS", "NORM", "STR", "TUM")
TUMOUR = CLASSES.index("TUM")
TILE = 224
SOURCES = {"train": ("NCT_CRC_HE_100K_NONORM", 100_000), "heldout": ("CRC_VAL_HE_7K", 7_180)}
SEED = 0


def list_shards(prefix: str) -> list:
    """[(path, sha256)] of one source's Parquet shards, in order."""
    with urllib.request.urlopen(TREE_URL) as response:
        files = json.load(response)
    return sorted((f["path"], f["lfs"]["oid"]) for f in files if Path(f["path"]).name.startswith(f"{prefix}-"))


def fetch_shard(path: str, sha256: str, data_dir: Path) -> Path:
    dest = data_dir / Path(path).name
    if dest.exists() and sha256sum(dest) == sha256:
        return dest
    download(FILE_URL.format(path=path), dest)
    if sha256sum(dest) != sha256:
        dest.unlink()
        raise RuntimeError(f"SHA-256 mismatch for {path}; deleted it, run again to re-download")
    return dest


def decode(data: bytes) -> np.ndarray:
    """TIFF / PNG bytes -> RGB uint8 (224, 224, 3)."""
    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("undecodable image in shard")
    if bgr.shape[:2] != (TILE, TILE):
        raise ValueError(f"expected {TILE}x{TILE} tiles, got {bgr.shape[:2]}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def read_source(source: str, data_dir: Path, shards: list):
    """Yield (images, classes) batches of one source, downloading its shards one at a time.

    Appends each shard's path to `shards`; the caller deletes them once the split is written.
    """
    prefix, _ = SOURCES[source]
    for path, sha in list_shards(prefix):
        shard = fetch_shard(path, sha, data_dir)
        shards.append(shard)
        print(f"  converting {shard.name}", flush=True)
        for batch in pq.ParquetFile(shard).iter_batches(batch_size=1024, columns=["image", "label"]):
            images = np.stack([decode(img["bytes"]) for img in batch.column("image").to_pylist()])
            yield images, batch.column("label").to_numpy(zero_copy_only=False).astype(np.uint8)


def write_split(split: str, batches, n: int, data_dir: Path, dataset: str = "nct_crc", class_names=CLASSES) -> None:
    """Write one split from an iterable of (images, classes) batches with n rows in total.

    y is 1 for the "TUM" class; cls keeps the class index into class_names.
    """
    tumour = class_names.index("TUM")
    x_path, y_path = split_paths(split, data_dir, dataset)
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
        fy.create_dataset("y", data=(classes == tumour).astype(np.uint8))
        fy.create_dataset("cls", data=classes)
        fy.attrs["classes"] = ",".join(class_names)
    x_tmp.replace(x_path)
    y_tmp.replace(y_path)
    print(f"  {split}: {n} tiles, {np.mean(classes == tumour):.1%} tumour")


def convert_train(data_dir: Path) -> None:
    if all(p.exists() for p in split_paths("train", data_dir, "nct_crc")):
        print("[train] already present")
        return
    print("[train]")
    shards = []
    write_split("train", read_source("train", data_dir, shards), SOURCES["train"][1], data_dir)
    for shard in shards:
        shard.unlink()


def heldout_halves(classes: np.ndarray, seed: int = SEED) -> tuple:
    """(valid, test) index arrays: each class split in half at random."""
    rng = np.random.default_rng(seed)
    valid, test = [], []
    for c in np.unique(classes):
        idx = rng.permutation(np.flatnonzero(classes == c))
        valid.append(idx[: len(idx) // 2])
        test.append(idx[len(idx) // 2:])
    return np.sort(np.concatenate(valid)), np.sort(np.concatenate(test))


def convert_heldout(data_dir: Path) -> None:
    if all(p.exists() for s in ("valid", "test") for p in split_paths(s, data_dir, "nct_crc")):
        print("[valid, test] already present")
        return
    print("[valid, test]")
    shards = []
    images, classes = zip(*read_source("heldout", data_dir, shards))
    images, classes = np.concatenate(images), np.concatenate(classes)
    _, n = SOURCES["heldout"]
    if len(classes) != n:
        raise RuntimeError(f"CRC-VAL-HE-7K: expected {n} images, got {len(classes)}")
    for split, idx in zip(("valid", "test"), heldout_halves(classes)):
        write_split(split, [(images[idx], classes[idx])], len(idx), data_dir)
    for shard in shards:
        shard.unlink()


def shuffle_split(split: str, data_dir: Path, seed: int = SEED, chunk: int = 2048, dataset: str = "nct_crc") -> None:
    """Rewrite a split in a fixed random order, once (marked in the y file).

    The sources are sorted by class, so without this the first N tiles (--limit smoke runs,
    quick checks) would all be one tissue class.
    """
    x_path, y_path = split_paths(split, data_dir, dataset)
    with h5py.File(y_path, "r") as fy:
        if fy.attrs.get("order") == f"shuffled, seed {seed}":
            return
        labels = {name: fy[name][:] for name in fy}  # y, cls and any other per-tile arrays
        attrs = dict(fy.attrs)
    print(f"  shuffling {split}", flush=True)
    order = np.random.default_rng(seed).permutation(len(labels["y"]))
    x_tmp, y_tmp = (p.with_name(p.name + ".tmp") for p in (x_path, y_path))
    with h5py.File(x_path, "r") as fx, h5py.File(x_tmp, "w") as out:
        src = fx["x"]
        # Contiguous and uncompressed (as written above), so read it through a memmap.
        images = np.memmap(x_path, dtype=src.dtype, mode="r", offset=src.id.get_offset(), shape=src.shape)
        x = out.create_dataset("x", shape=src.shape, dtype=src.dtype)
        for i in range(0, len(order), chunk):
            x[i:i + chunk] = images[order[i:i + chunk]]
        del images
    with h5py.File(y_tmp, "w") as fy:
        for name, values in labels.items():
            fy.create_dataset(name, data=values[order])
        fy.attrs.update(attrs)
        fy.attrs["order"] = f"shuffled, seed {seed}"
    x_tmp.replace(x_path)
    y_tmp.replace(y_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DATASETS["nct_crc"]["dir"])
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    convert_heldout(args.data_dir)  # small, so a quick sanity check is possible before train finishes
    convert_train(args.data_dir)
    for split in ("valid", "test", "train"):
        shuffle_split(split, args.data_dir)
    print(f"Done: {args.data_dir}")


if __name__ == "__main__":
    main()
