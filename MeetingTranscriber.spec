# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
import faster_whisper

block_cipher = None

project_root = Path(globals().get("SPECPATH", os.getcwd())).resolve()

def add_dir_to_datas(src_dir: Path, dest_root: str, datas: list):
    if not src_dir.exists():
        return
    for p in src_dir.rglob("*"):
        if p.is_file():
            rel_parent = p.relative_to(src_dir).parent
            dest = os.path.join(dest_root, str(rel_parent)) if str(rel_parent) != "." else dest_root
            datas.append((str(p), dest))

datas = []

assets_dir = project_root / "assets"
add_dir_to_datas(assets_dir, "assets", datas)

fw_pkg_dir = Path(faster_whisper.__file__).resolve().parent
fw_assets_dir = fw_pkg_dir / "assets"
add_dir_to_datas(fw_assets_dir, os.path.join("faster_whisper", "assets"), datas)

hiddenimports = [
    "requests",
    "docx",
    "lxml",
    "PIL",
    "ctranslate2",
    "faster_whisper",
    "sounddevice",
    "soundfile",
    "numpy",
    "av",
    "onnxruntime",
    "tokenizers",
    "meetingtranscriber.core.summarization_service",
    "meetingtranscriber.core.word_exporter",
    "meetingtranscriber.core.recording_service",
]

a = Analysis(
    ["meetingtranscriber/main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="alsa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(assets_dir / "app.ico") if (assets_dir / "app.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="alsa",
)