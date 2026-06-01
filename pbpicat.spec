# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PBPicat.

  Linux   → dist/PBPicat-<version>-linux-x86_64
  Windows → dist/PBPicat-<version>-windows-x86_64.exe
  macOS   → dist/PBPicat-<version>-macos-arm64.app

Build with:  make dist
"""

import os
import platform
import sys
from pathlib import Path

_version = os.environ.get("PBPICAT_VERSION", "dev")

_machine = platform.machine().lower()
_arch = {
    "x86_64": "x86_64",
    "amd64":  "x86_64",
    "arm64":  "arm64",
    "aarch64": "arm64",
}.get(_machine, _machine)

if sys.platform == "linux":
    _os = "linux"
elif sys.platform == "win32":
    _os = "windows"
elif sys.platform == "darwin":
    _os = "macos"
else:
    _os = sys.platform

_artifact_name = f"PBPicat-{_version}-{_os}-{_arch}"

_locale_root = Path("src/pbpicat/locale")
_datas = [
    (str(mo), f"pbpicat/locale/{mo.parts[-3]}/LC_MESSAGES")
    for mo in sorted(_locale_root.glob("*/LC_MESSAGES/pbpicat.mo"))
] + [
    (str(svg), "resources")
    for svg in sorted(Path("src/pbpicat/resources").glob("*.svg"))
]

a = Analysis(
    ["src/pbpicat/__main__.py"],
    pathex=["src"],
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "email", "http", "xml", "numpy", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=_artifact_name,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name=_artifact_name,
    )
    BUNDLE(
        coll,
        name=f"{_artifact_name}.app",
        bundle_identifier="net.cardolan.pbpicat",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": _version,
            "CFBundleName": "PBPicat",
        },
    )
else:
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name=_artifact_name,
        console=False,
    )
