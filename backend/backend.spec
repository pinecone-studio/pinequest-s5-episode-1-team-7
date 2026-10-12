# -*- mode: python ; coding: utf-8 -*-
# Build:  pip install pyinstaller && pyinstaller backend.spec   ->  dist/triage-backend
# The AI engine (../engine) is imported dynamically, so it is bundled explicitly below.
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("uvicorn") + collect_submodules("engine")

a = Analysis(
    ["run_server.py"],
    pathex=[".", ".."],          # ".." makes the sibling engine/ package importable
    hiddenimports=hidden,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="triage-backend", console=True)
