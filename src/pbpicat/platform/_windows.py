"""Windows file-open helpers."""

from __future__ import annotations

import os
from pathlib import Path


def open_default(path: Path) -> None:
    os.startfile(str(path))


def open_with(path: Path, parent=None) -> None:
    try:
        os.startfile(str(path), "openas")
    except OSError:
        open_default(path)
