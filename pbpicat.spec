# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PBPicat.

  Linux   → dist/pbpicat-<version>-linux-x86_64
  Windows → dist/pbpicat-<version>-windows-x86_64.exe
  macOS   → dist/pbpicat-<version>-macos-arm64.app

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

_artifact_name = f"pbpicat-{_version}-{_os}-{_arch}"

import shutil as _shutil
_jpegtran = _shutil.which("jpegtran")
_binaries = [(_jpegtran, ".")] if _jpegtran else []

# pyexiv2 loads its native libs via ctypes.CDLL() with a dynamically built path
# (pyexiv2/lib/__init__.py), so PyInstaller's static import analysis never
# discovers them and they must be collected here explicitly.
# find_spec() locates the package without importing it: importing pyexiv2.lib
# would run its ctypes.CDLL() call here too, on the build machine.
import importlib.util as _importlib_util

_pyexiv2_spec = _importlib_util.find_spec("pyexiv2")
_pyexiv2_lib_dir = Path(_pyexiv2_spec.origin).parent / "lib"
_binaries += [
    (str(f), "pyexiv2/lib")
    for f in sorted(_pyexiv2_lib_dir.iterdir())
    if f.suffix in (".so", ".dylib", ".dll", ".pyd")
]

from PyInstaller.utils.hooks import copy_metadata

_locale_root = Path("src/pbpicat/locale")
_datas = copy_metadata("pbpicat") + [
    (str(mo), f"pbpicat/locale/{mo.parts[-3]}/LC_MESSAGES")
    for mo in sorted(_locale_root.glob("*/LC_MESSAGES/pbpicat.mo"))
] + [
    (str(svg), "resources")
    for svg in sorted(Path("src/pbpicat/resources").glob("*.svg"))
]

# Conda fonts: bundled to guarantee identical rendering across machines.
# On Linux, fontconfig resolves fonts via absolute paths written into fonts.conf
# at build time; those paths do not exist on the target machine.
# The runtime hook hooks/pyi_rth_fonts.py generates a portable fonts.conf at startup.
_conda_fonts = Path(sys.prefix) / "fonts"
if _conda_fonts.is_dir():
    _datas += [(str(_conda_fonts), "fonts")]

a = Analysis(
    ["src/pbpicat/__main__.py"],
    pathex=["src"],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=["hooks/pyi_rth_fonts.py"],
    excludes=["tkinter", "unittest", "http", "xml", "numpy", "matplotlib"],
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
