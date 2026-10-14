"""Patch dataset loading (PCam and other organs) and GPU augmentation.

Every dataset is stored in PCam's HDF5 layout: <stem>_x.h5 with x (N, H, W, 3) uint8 and
<stem>_y.h5 with y (N, ...) 0/1 tumour labels, one pair per split. So one loader, train.py
and teacher.py work for every organ (issue #53); only DATASETS below differs.

Images are read a whole batch at a time (one worker call per batch) and augmented on the
GPU, which keeps the CPU from becoming the bottleneck, especially on Windows.
"""
from pathlib import Path

import h5py
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import BatchSampler, DataLoader, Dataset, RandomSampler, SequentialSampler

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DATA_DIR = DATA_ROOT / "pcam"
SPLITS = ("train", "valid", "test")
PCAM_SIZE = 96

# name -> where its HDF5 files are, the organ its model is for, and the prefix of the
# checkpoint / results file names (pcam_..., colon_...).
DATASETS = {
    "pcam": {
        "dir": DATA_DIR,
        "stem": "camelyonpatch_level_2_split_{split}",
        "organ": "lymph_node",
        "prefix": "pcam",
        "short": "PCam",
        "description": "PatchCamelyon (PCam), CC0, via Hugging Face 1aurent/PatchCamelyon",
    },
    "nct_crc": {  # training/download_nct_crc.py
        "dir": DATA_ROOT / "nct-crc",
        "stem": "nct_crc_split_{split}",
        "organ": "colon",
        "prefix": "colon",
        "short": "NCT-CRC-HE",
        "description": "NCT-CRC-HE-100K-NONORM (train) + CRC-VAL-HE-7K halves (valid / test), CC BY 4.0, "
                       "via Hugging Face 1aurent/NCT-CRC-HE",
    },
    "hmu_gc": {  # training/download_hmu_gc.py
        "dir": DATA_ROOT / "hmu-gc",
        "stem": "hmu_gc_split_{split}",
        "organ": "stomach",
        "prefix": "stomach",
        "short": "HMU-GC-HE-30K",
        "description": "HMU-GC-HE-30K (gastric cancer, 300 slides), contiguous-block train / valid / test split, "
                       "CC BY 4.0, via figshare 10.6084/m9.figshare.25954813",
    },
}


def split_paths(split: str, data_dir: Path = None, dataset: str = "pcam") -> tuple:
    spec = DATASETS[dataset]
    stem = Path(data_dir or spec["dir"]) / spec["stem"].format(split=split)
    return Path(f"{stem}_x.h5"), Path(f"{stem}_y.h5")


class PCamBatches(Dataset):
    """Indexed by a list of sample indices; returns (uint8 images NHWC, float labels).

    Uncompressed contiguous HDF5 is read through np.memmap (much faster for random access
    than h5py point selection); anything else falls back to h5py.
    """

    def __init__(self, x_path: Path, y_path: Path, limit: int = 0):
        with h5py.File(y_path, "r") as f:
            self.labels = f["y"][:].reshape(-1).astype(np.float32)
        if limit:
            self.labels = self.labels[:limit]
        self.x_path = Path(x_path)
        self._images = None  # opened lazily, once per worker process
        self.soft = None     # optional per-sample teacher logits for distillation (set by train.py)

    @classmethod
    def from_split(cls, split: str, data_dir: Path = None, limit: int = 0, dataset: str = "pcam") -> "PCamBatches":
        return cls(*split_paths(split, data_dir, dataset), limit=limit)

    def __len__(self) -> int:
        return len(self.labels)

    def _open(self):
        f = h5py.File(self.x_path, "r")
        x = f["x"]
        offset = x.id.get_offset()
        if offset is not None and x.compression is None and x.chunks is None:
            self._images = np.memmap(self.x_path, dtype=x.dtype, mode="r", offset=offset, shape=x.shape)
            f.close()
        else:
            self._images = x  # keep the file open for h5py reads

    def __getitem__(self, indices):
        if self._images is None:
            self._open()
        idx = np.sort(np.asarray(indices))  # h5py needs increasing indices
        images = np.ascontiguousarray(self._images[idx])
        if self.soft is not None:
            return torch.from_numpy(images), torch.from_numpy(self.labels[idx]), torch.from_numpy(self.soft[idx])
        return torch.from_numpy(images), torch.from_numpy(self.labels[idx])


def make_loader(dataset: PCamBatches, batch_size: int, shuffle: bool, workers: int) -> DataLoader:
    sampler = RandomSampler(dataset) if shuffle else SequentialSampler(dataset)
    return DataLoader(
        dataset,
        sampler=BatchSampler(sampler, batch_size, drop_last=shuffle),
        batch_size=None,  # the sampler already yields batches
        num_workers=workers,
        pin_memory=True,
        persistent_workers=workers > 0,
    )


def to_input(images: torch.Tensor, device, img_size: int = PCAM_SIZE) -> torch.Tensor:
    """uint8 NHWC RGB -> float NCHW in [0, 1] on device, resized to img_size."""
    x = images.to(device, non_blocking=True).permute(0, 3, 1, 2).float().div_(255.0)
    if img_size != x.shape[-1]:
        x = F.interpolate(x, size=(img_size, img_size), mode="bilinear", align_corners=False)
    return x.contiguous(memory_format=torch.channels_last)


# Optical densities of haematoxylin, eosin and DAB (Ruifrok & Johnston; same matrix as skimage).
RGB_FROM_HED = torch.tensor([[0.65, 0.70, 0.29], [0.07, 0.99, 0.11], [0.27, 0.57, 0.78]])
RGB_FROM_HED = RGB_FROM_HED / RGB_FROM_HED.norm(dim=1, keepdim=True)
HED_FROM_RGB = torch.linalg.inv(RGB_FROM_HED)


def _uniform(n, low, high, device, *shape):
    return low + (high - low) * torch.rand(n, *shape, device=device)


def _dihedral(x: torch.Tensor, n: int) -> torch.Tensor:
    """Random flips/transpose per sample: all 8 orientations (tissue has no 'up')."""
    def coin():
        return torch.rand(n, 1, 1, 1, device=x.device) < 0.5

    if x.shape[-1] == x.shape[-2]:
        x = torch.where(coin(), x.transpose(-1, -2), x)
    x = torch.where(coin(), x.flip(-1), x)
    return torch.where(coin(), x.flip(-2), x)


def _rotate_zoom(x: torch.Tensor, n: int, max_zoom: float) -> torch.Tensor:
    """Arbitrary rotation and +-max_zoom scaling around the centre (PCam's label is about
    the centre 32x32, which stays in view), with mirrored borders."""
    angle = _uniform(n, 0, 2 * torch.pi, x.device)
    scale = _uniform(n, 1 - max_zoom, 1 + max_zoom, x.device)
    cos, sin = torch.cos(angle) / scale, torch.sin(angle) / scale
    zero = torch.zeros_like(cos)
    theta = torch.stack([torch.stack([cos, -sin, zero], 1), torch.stack([sin, cos, zero], 1)], 1)
    grid = F.affine_grid(theta, list(x.shape), align_corners=False)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=False)


def _stain_jitter(x: torch.Tensor, n: int, sigma: float, bias: float) -> torch.Tensor:
    """Scale and shift the H, E and D stain concentrations per sample (Tellez et al. 2018).

    Imitates staining differences between labs far more realistically than RGB jitter.
    """
    m_in, m_out = HED_FROM_RGB.to(x.device), RGB_FROM_HED.to(x.device)
    od = -torch.log(x.clamp(min=1e-6))                         # optical density, NCHW
    hed = torch.einsum("nchw,cd->ndhw", od, m_in)
    hed = hed * _uniform(n, 1 - sigma, 1 + sigma, x.device, 3, 1, 1) + _uniform(n, -bias, bias, x.device, 3, 1, 1)
    return torch.exp(-torch.einsum("ndhw,dc->nchw", hed, m_out))


def _colour_jitter(x: torch.Tensor, n: int, strength: float) -> torch.Tensor:
    """Brightness, contrast and saturation: lighting and white-balance differences."""
    def factor():
        return _uniform(n, 1 - strength, 1 + strength, x.device, 1, 1, 1)

    gray = 0.299 * x[:, 0:1] + 0.587 * x[:, 1:2] + 0.114 * x[:, 2:3]
    x = gray + (x - gray) * factor()
    mean = x.mean(dim=(1, 2, 3), keepdim=True)
    x = mean + (x - mean) * factor()
    return x * factor()


def _blur(x: torch.Tensor, n: int, p: float, max_sigma: float, size: int = 5) -> torch.Tensor:
    """Gaussian blur on a random fraction p of the batch: slightly out-of-focus captures."""
    sigma = _uniform(n, 0.3, max_sigma, x.device) * (torch.rand(n, device=x.device) < p)
    r = torch.arange(size, device=x.device, dtype=x.dtype) - size // 2
    k1 = torch.exp(-(r[None] ** 2) / (2 * sigma[:, None].clamp(min=1e-3) ** 2))
    k1 = k1 / k1.sum(dim=1, keepdim=True)
    kernels = (k1[:, :, None] * k1[:, None, :]).repeat_interleave(3, dim=0)[:, None]  # (3n, 1, k, k)
    c, h, w = x.shape[1:]
    out = F.conv2d(F.pad(x.reshape(1, n * c, h, w), [size // 2] * 4, mode="reflect"), kernels, groups=n * c)
    return out.reshape(n, c, h, w)


def augment(x: torch.Tensor, strength: float = 1.0) -> torch.Tensor:
    """Random geometry, stain, lighting, focus and sensor-noise changes on an NCHW [0, 1] batch.

    Beyond regularising PCam training, blur, noise and colour shifts mimic smartphone
    captures through an eyepiece, which look different from PCam's slide-scanner images.
    strength scales all colour, blur and noise ranges (0 = geometry only).
    """
    n = x.shape[0]
    x = _dihedral(x, n)
    x = _rotate_zoom(x, n, max_zoom=0.1)
    x = _stain_jitter(x.clamp(0, 1), n, sigma=0.05 * strength, bias=0.05 * strength)
    x = _colour_jitter(x.clamp(0, 1), n, strength=0.15 * strength)
    x = _blur(x.clamp(0, 1), n, p=0.3 * min(strength, 1.0), max_sigma=1.0 + 0.5 * strength)
    x = x + torch.randn_like(x) * _uniform(n, 0, 0.02 * strength, x.device, 1, 1, 1)
    return x.clamp_(0.0, 1.0).contiguous(memory_format=torch.channels_last)
