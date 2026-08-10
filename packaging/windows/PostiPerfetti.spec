from pathlib import Path
import runpy

# Questo file vive in packaging/windows/.
# SPECPATH è fornito da PyInstaller e rende la build indipendente dal
# percorso assoluto in cui il repository è stato clonato.
PACKAGING_DIR = Path(SPECPATH).resolve()
ROOT = PACKAGING_DIR.parents[1]

# La versione viene letta dalla fonte unica dell'applicazione.
_dati_versione = runpy.run_path(
    str(ROOT / "moduli" / "versione.py")
)
VERSIONE_WINDOWS = tuple(_dati_versione["VERSIONE_WINDOWS"])
VERSIONE_WINDOWS_TESTO = ".".join(
    str(parte) for parte in VERSIONE_WINDOWS
)

ENTRY_POINT = ROOT / "postiperfetti.py"
RISORSE = ROOT / "risorse"
ICONA = PACKAGING_DIR / "postiperfetti.ico"

# PyInstaller richiede un Version resource Windows. Lo generiamo durante
# la build, così nessun numero di versione resta duplicato nel packaging.
VERSION_INFO = ROOT / "build" / "version_info.generated.txt"
VERSION_INFO.parent.mkdir(parents=True, exist_ok=True)
VERSION_INFO.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSIONE_WINDOWS!r},
    prodvers={VERSIONE_WINDOWS!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'041004B0',
          [
            StringStruct(u'CompanyName', u'Omar Ceretta'),
            StringStruct(u'FileDescription', u'PostiPerfetti — Assegnazione automatica dei posti in classe'),
            StringStruct(u'FileVersion', u'{VERSIONE_WINDOWS_TESTO}'),
            StringStruct(u'InternalName', u'PostiPerfetti'),
            StringStruct(u'LegalCopyright', u'© 2026 Omar Ceretta — GNU GPLv3'),
            StringStruct(u'OriginalFilename', u'PostiPerfetti.exe'),
            StringStruct(u'ProductName', u'PostiPerfetti'),
            StringStruct(u'ProductVersion', u'{VERSIONE_WINDOWS_TESTO}'),
            StringStruct(u'Comments', u'Software libero per docenti — GNU GPLv3'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1040, 1200])])
  ]
)
""",
    encoding="utf-8",
)

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
