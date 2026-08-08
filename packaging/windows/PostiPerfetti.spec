# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

# Questo file vive in packaging/windows/.
# SPECPATH è fornito da PyInstaller e rende la build indipendente dal
# percorso assoluto in cui il repository è stato clonato.
PACKAGING_DIR = Path(SPECPATH).resolve()
ROOT = PACKAGING_DIR.parents[1]

ENTRY_POINT = ROOT / "postiperfetti.py"
RISORSE = ROOT / "risorse"
ICONA = PACKAGING_DIR / "postiperfetti.ico"
VERSION_INFO = PACKAGING_DIR / "version_info.txt"

a = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(RISORSE), "risorse"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PostiPerfetti",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICONA),
    version=str(VERSION_INFO),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PostiPerfetti",
)
