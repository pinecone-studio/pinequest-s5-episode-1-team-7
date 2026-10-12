"""Download PatchCamelyon (PCam) and unpack it to engine/data/pcam/ as HDF5.

PCam: 327,680 96x96 RGB patches of lymph node sections (H&E), labelled 1 if the centre
32x32 region contains metastatic tumour tissue. License: CC0. https://github.com/basveeling/pcam

The official Zenodo record (2546921) throttles to ~50 KB/s, so this pulls the Hugging Face
mirror (1aurent/PatchCamelyon, Parquet with PNG-encoded images, pinned revision) and
converts each split to the original layout: camelyonpatch_level_2_split_<split>_{x,y}.h5
with x (N, 96, 96, 3) uint8 and y (N, 1, 1, 1) uint8. Downloads resume if interrupted and
are checked against their SHA-256. Parquet shards are deleted once their split is converted.

    python -m training.download_pcam                  # all splits (~7.6 GB download)
    python -m training.download_pcam --splits valid test
"""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import cv2
import h5py
import numpy as np
import pyarrow.parquet as pq

from training.pcam import DATA_DIR, PCAM_SIZE, split_paths

REPO = "1aurent/PatchCamelyon"
REVISION = "e4bd149e7a868a9d811fdd9f9a9fb78c05c104ab"
TREE_URL = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}/data"
FILE_URL = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{{path}}"
SPLIT_SIZES = {"train": 262144, "valid": 32768, "test": 32768}
CHUNK = 1 << 20


def list_shards(split: str) -> list:
    """[(path, sha256)] of the split's Parquet shards, in order."""
    with urllib.request.urlopen(TREE_URL) as response:
        files = json.load(response)
    shards = [(f["path"], f["lfs"]["oid"]) for f in files if Path(f["path"]).name.startswith(f"{split}-")]
    return sorted(shards)


def download(url: str, dest: Path) -> None:
    """Download url to dest, resuming from a partial dest.part if one exists."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(request) as response:
        if have and response.status != 206:  # server ignored the range: start over
            have = 0
        total = have + int(response.headers.get("Content-Length", 0))
        with open(part, "ab" if have else "wb") as out:
            done = have
            while chunk := response.read(CHUNK):
                out.write(chunk)
                done += len(chunk)
                print(f"\r  {dest.name}: {done / 1e6:.0f} / {total / 1e6:.0f} MB", end="", flush=True)
    print()
    part.replace(dest)


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_shard(path: str, sha256: str, data_dir: Path) -> Path:
    dest = data_dir / Path(path).name
    if dest.exists() and sha256sum(dest) == sha256:
        return dest
    download(FILE_URL.format(path=path), dest)
    if sha256sum(dest) != sha256:
        dest.unlink()
        raise RuntimeError(f"SHA-256 mismatch for {path}; deleted it, run again to re-download")
    return dest


def decode_png(data: bytes) -> np.ndarray:
    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None or bgr.shape != (PCAM_SIZE, PCAM_SIZE, 3):
        raise ValueError("unexpected image in shard")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def convert_split(split: str, data_dir: Path) -> None:
    x_path, y_path = split_paths(split, data_dir)
    if x_path.exists() and y_path.exists():
        print(f"[{split}] already present")
        return
    print(f"[{split}]")
    shards = [fetch_shard(path, sha, data_dir) for path, sha in list_shards(split)]

    n = SPLIT_SIZES[split]
    x_tmp, y_tmp = (p.with_name(p.name + ".tmp") for p in (x_path, y_path))
    labels = np.zeros(n, dtype=np.uint8)
    with h5py.File(x_tmp, "w") as fx:
        # Contiguous and uncompressed, so training can memory-map it (see pcam.PCamBatches).
        x = fx.create_dataset("x", shape=(n, PCAM_SIZE, PCAM_SIZE, 3), dtype=np.uint8)
        i = 0
        for shard in shards:
            print(f"  converting {shard.name}", flush=True)
            for batch in pq.ParquetFile(shard).iter_batches(batch_size=4096, columns=["image", "label"]):
                images = batch.column("image").to_pylist()
                x[i:i + len(images)] = np.stack([decode_png(img["bytes"]) for img in images])
                labels[i:i + len(images)] = batch.column("label").to_numpy(zero_copy_only=False)
                i += len(images)
    if i != n:
        x_tmp.unlink()
        raise RuntimeError(f"{split}: expected {n} images, got {i}")
    with h5py.File(y_tmp, "w") as fy:
        fy.create_dataset("y", data=labels.reshape(n, 1, 1, 1))

    x_tmp.replace(x_path)
    y_tmp.replace(y_path)
    for shard in shards:
        shard.unlink()
    print(f"  {n} images, {labels.mean():.1%} tumour")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--splits", nargs="+", choices=list(SPLIT_SIZES), default=list(SPLIT_SIZES))
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    # Smallest splits first, so a quick sanity check is possible before train finishes.
    for split in sorted(args.splits, key=lambda s: s == "train"):
        convert_split(split, args.data_dir)
    print(f"Done: {args.data_dir}")


if __name__ == "__main__":
    main()
