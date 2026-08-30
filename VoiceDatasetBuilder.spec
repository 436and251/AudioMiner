import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hiddenimports = ["ssl", "_ssl"]
datas = [("assets/app.ico", "assets")]
binaries = []

python_root = Path(sys.base_prefix)

openssl_patterns = (
    "libssl*.dll",
    "libcrypto*.dll",
)

for search_dir in (
    python_root,
    python_root / "DLLs",
    python_root / "Library" / "bin",
):
    if not search_dir.exists():
        continue

    for pattern in openssl_patterns:
        for dll in search_dir.glob(pattern):
            binaries.append((str(dll), "."))

for package in ("demucs", "faster_whisper"):
    hiddenimports += collect_submodules(package)
    datas += collect_data_files(package)

for package in ("ctranslate2", "torch"):
    binaries += collect_dynamic_libs(package)

analysis = Analysis(
    ["voice_dataset_builder.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="VoiceDatasetBuilder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app.ico",
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="VoiceDatasetBuilder",
)
