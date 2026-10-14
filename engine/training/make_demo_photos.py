"""Build the demo photos in demo/ from real PCam lymph-node patches.

PCam has no whole slides, so each demo photo is a mosaic of 96 px PCam test patches
(~0.97 µm/px) inside a round eyepiece-style field, the same style as the browser-test
fixture. Tumour patches are placed as one contiguous region so the heatmap shows a clear
hotspot. Patches are picked where the shipped model agrees confidently with the PCam label,
so the demo is predictable: these photos show the workflow, they are NOT an accuracy test.

Also writes a synthetic stage-micrometer photo at the same scale, so calibration can be
demoed: click the 0 and 1000 µm marks and enter 1000 µm (-> ~0.97 µm/px).

Downloads one PCam test shard (~376 MB, SHA-256 checked) into engine/data/pcam-demo/.

    python -m training.make_demo_photos
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq

from pipeline.inference import DEFAULT_MODEL_PATH, PatchClassifier
from training.download_pcam import decode_png, fetch_shard, list_shards
from training.pcam import PCAM_SIZE

ENGINE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ENGINE_DIR.parent / "demo"
DATA_DIR = ENGINE_DIR / "data" / "pcam-demo"

UM_PER_PX = 0.972  # PCam: Camelyon16 level 2 (0.243 µm/px x 4)
ROWS, COLS = 12, 16  # 1152 x 1536 px photo
CANDIDATES = 6000    # test patches scored to pick from
NORMAL_MAX_P, TUMOUR_MIN_P = 0.05, 0.95

# name -> (tumour region as (centre row, centre col, radius) in patch units or None, seed).
# Seeds are fixed per photo so each one is reproducible; the flags they get from the
# shipped model are listed in demo/README.md.
PHOTOS = {
    "01-normal-lymph-node": (None, 7),
    "02-micro-metastasis": ((5.5, 11.0, 0.6), 11),
    "03-small-metastasis": ((4.0, 10.5, 2.2), 7),
    "04-large-metastasis": ((6.0, 7.0, 3.6), 7),
}


def load_candidates(shard: Path, n: int) -> tuple:
    images, labels = [], []
    for batch in pq.ParquetFile(shard).iter_batches(batch_size=2048, columns=["image", "label"]):
        images += [decode_png(img["bytes"]) for img in batch.column("image").to_pylist()]
        labels += batch.column("label").to_pylist()
        if len(images) >= n:
            break
    return np.stack(images[:n]), np.array(labels[:n])


def eyepiece_mask(height: int, width: int) -> np.ndarray:
    """1 inside a round field of view with a soft edge and slight fall-off, 0 outside."""
    y, x = np.mgrid[:height, :width]
    r = np.hypot((x - width / 2) / (0.52 * width), (y - height / 2) / (0.52 * width))
    field = np.clip((1.0 - r) / 0.04, 0.0, 1.0)
    return field * (1.0 - 0.18 * np.clip(r, 0, 1) ** 2)


def finish(photo: np.ndarray) -> np.ndarray:
    mask = eyepiece_mask(*photo.shape[:2])[..., None]
    return np.clip(photo.astype(np.float32) * mask, 0, 255).astype(np.uint8)


def mosaic(normal: np.ndarray, tumour: np.ndarray, region, rng) -> tuple:
    photo = np.zeros((ROWS * PCAM_SIZE, COLS * PCAM_SIZE, 3), dtype=np.uint8)
    n_tumour = 0
    normal_idx = rng.permutation(len(normal))
    tumour_idx = rng.permutation(len(tumour))
    for row in range(ROWS):
        for col in range(COLS):
            in_region = region is not None and np.hypot(row + 0.5 - region[0], col + 0.5 - region[1]) <= region[2]
            if in_region:
                patch = tumour[tumour_idx[n_tumour % len(tumour)]]
                n_tumour += 1
            else:
                patch = normal[normal_idx[(row * COLS + col) % len(normal)]]
            photo[row * PCAM_SIZE:(row + 1) * PCAM_SIZE, col * PCAM_SIZE:(col + 1) * PCAM_SIZE] = patch
    return finish(photo), n_tumour


def micrometer() -> np.ndarray:
    """Stage micrometer: 1 mm scale in 10 µm steps, numbered every 100 µm."""
    height, width = ROWS * PCAM_SIZE, COLS * PCAM_SIZE
    photo = np.full((height, width, 3), (236, 232, 222), dtype=np.uint8)
    px_per_um = 1.0 / UM_PER_PX
    x0, y = int(width / 2 - 500 * px_per_um), height // 2
    ink = (40, 40, 40)
    cv2.line(photo, (x0, y), (int(x0 + 1000 * px_per_um), y), ink, 2, cv2.LINE_AA)
    for um in range(0, 1001, 10):
        x = int(round(x0 + um * px_per_um))
        length = 60 if um % 100 == 0 else 38 if um % 50 == 0 else 22
        cv2.line(photo, (x, y), (x, y - length), ink, 2, cv2.LINE_AA)
        if um % 100 == 0:
            label = str(um)
            (w, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.putText(photo, label, (x - w // 2, y + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ink, 2, cv2.LINE_AA)
    cv2.putText(photo, "1 DIV = 0.01 mm", (x0, y + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ink, 2, cv2.LINE_AA)
    return finish(photo)


def save(path: Path, rgb: np.ndarray) -> None:
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=OUT_DIR)
    args = p.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path, sha = list_shards("test")[0]
    shard = fetch_shard(path, sha, DATA_DIR)
    images, labels = load_candidates(shard, CANDIDATES)
    probs = PatchClassifier(DEFAULT_MODEL_PATH).predict(images)
    normal = images[(labels == 0) & (probs <= NORMAL_MAX_P)]
    tumour = images[(labels == 1) & (probs >= TUMOUR_MIN_P)]
    print(f"{len(normal)} confident normal and {len(tumour)} confident tumour patches")

    args.out.mkdir(parents=True, exist_ok=True)
    save(args.out / "00-stage-micrometer.jpg", micrometer())
    for name, (region, seed) in PHOTOS.items():
        photo, n_tumour = mosaic(normal, tumour, region, np.random.default_rng(seed))
        save(args.out / f"{name}.jpg", photo)
        print(f"{name}: {n_tumour} tumour patches of {ROWS * COLS}")


if __name__ == "__main__":
    main()
