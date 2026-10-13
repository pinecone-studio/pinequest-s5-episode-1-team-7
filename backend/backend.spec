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

a = Analysis(
    ["run_server.py"],
    pathex=[".", ".."],          # ".." makes the sibling engine/ package importable
    hiddenimports=hidden,
    # The ONNX model, at the path engine/pipeline/inference.py expects (engine/model/).
    datas=[(os.path.join(ROOT, "engine", "model", "model_fp32.onnx"), os.path.join("engine", "model"))],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="triage-backend", console=True)
