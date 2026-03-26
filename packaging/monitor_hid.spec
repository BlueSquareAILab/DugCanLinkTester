# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

if importlib.util.find_spec("vgamepad") is None:
    raise SystemExit(
        "MonitorHID build requires `uv sync --group build --extra hid` before running PyInstaller."
    )

project_root = Path.cwd()
readme_file = project_root / "README.md"
entry_script = project_root / "main.py"

datas = collect_data_files("vgamepad")
if readme_file.exists():
    datas.append((str(readme_file), "."))

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("vgamepad"),
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
    name="DugCanLinkTesterMonitorHID",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DugCanLinkTester-MonitorHID-win64",
)
