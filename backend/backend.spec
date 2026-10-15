# -*- mode: python ; coding: utf-8 -*-
# Build:  pip install pyinstaller && pyinstaller backend.spec   ->  dist/triage-backend
# The AI engine (../engine) is imported dynamically, so it is bundled explicitly below.
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.dirname(SPECPATH)  # repo root: the parent of backend/

# collect_submodules() imports the package while this spec runs, so ../engine must be on sys.path
# here; `pathex` below only applies to the analysis step. Without this, "engine" is silently left
# out and the frozen backend falls back to the STUB scorer (made-up scores).
sys.path.insert(0, ROOT)
engine_modules = collect_submodules("engine", filter=lambda name: not name.startswith("engine.training"))
if "engine.pipeline" not in engine_modules:
    raise SystemExit("engine.pipeline not found: the AI engine would be missing from the build")

hidden = collect_submodules("uvicorn") + engine_modules

# Every organ's model + card (engine/model/<organ>/model_fp32.onnx + model_card.json),
# plus the lymph-node files at engine/model/ root: the packaged app must score any
# offered organ offline, at the paths engine/pipeline expects.
model_datas = []
model_root = os.path.join(ROOT, "engine", "model")
for dirpath, _dirnames, filenames in os.walk(model_root):
    for filename in sorted(filenames):
        if filename in ("model_fp32.onnx", "model_card.json"):
            rel = os.path.relpath(dirpath, model_root)
            dest = os.path.join("engine", "model") if rel == "." else os.path.join("engine", "model", rel)
            model_datas.append((os.path.join(dirpath, filename), dest))
if not [src for src, _ in model_datas if src.endswith(os.path.join("model", "model_fp32.onnx"))]:
    raise SystemExit("engine/model/model_fp32.onnx not found: the app would have no model")

a = Analysis(
    ["run_server.py"],
    pathex=[".", ".."],          # ".." makes the sibling engine/ package importable
    hiddenimports=hidden,
    datas=model_datas,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="triage-backend", console=True)
