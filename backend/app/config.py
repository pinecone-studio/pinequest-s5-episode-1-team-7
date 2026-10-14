"""Backend configuration. Every value can be overridden with an environment variable."""
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("TRIAGE_DATA_DIR", str(Path.home() / ".pathology-triage")))
IMAGES_DIR = DATA_DIR / "images"
HEATMAPS_DIR = DATA_DIR / "heatmaps"
DB_PATH = DATA_DIR / "triage.db"

# Salt for hashing patient IDs (TDD 7.1). Empty -> a random salt is generated once and
# stored in DATA_DIR/.salt (see anonymize.py).
HASH_SALT = os.getenv("TRIAGE_HASH_SALT", "")

# Fallback risk-flag thresholds on S_slide, used only when the engine does not return a flag.
# TODO(team): confirm the final Red/Yellow/Green thresholds (see docs/PLAN.md).
RED_THRESHOLD = float(os.getenv("TRIAGE_RED", "0.70"))
YELLOW_THRESHOLD = float(os.getenv("TRIAGE_YELLOW", "0.40"))

# "package.module:function" of Member 1's engine entry point (analyze_slide).
ENGINE_ENTRYPOINT = os.getenv("TRIAGE_ENGINE", "engine.pipeline:analyze_slide")
# How many slides may run inference at the same time (low-spec clinic PCs -> 1).
MAX_CONCURRENT_INFERENCE = max(1, int(os.getenv("TRIAGE_MAX_INFERENCE", "1")))

MAX_UPLOAD_MB = int(os.getenv("TRIAGE_MAX_UPLOAD_MB", "40"))

# Laplacian-variance blur gate, TDD 8.1 (see app/quality.py). <= 0 disables
# the check. There is no universal value (sharp real tiles score anywhere
# from ~10 to ~600 depending on setup), so calibrate per setup with
# `python -m app.quality sharp_dir/ blurry_dir/ [--um-per-px ..]` and set what
# it suggests. Slides ingested with a setup + objective are scored at the
# model's scale automatically. The default stays off until a validated value
# is configured (issue #40).
SHARPNESS_THRESHOLD = float(os.getenv("TRIAGE_SHARPNESS", "0"))

HOST = os.getenv("TRIAGE_HOST", "127.0.0.1")  # localhost only: offline-first
PORT = int(os.getenv("TRIAGE_PORT", "8000"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, IMAGES_DIR, HEATMAPS_DIR):
        d.mkdir(parents=True, exist_ok=True)
        try:  # patient data: keep other local users out (best effort, e.g. no-op on Windows)
            os.chmod(d, 0o700)
        except OSError:
            pass
