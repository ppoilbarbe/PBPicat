"""macOS file-open helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def config_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "pbpicat"


def open_default(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_with(path: Path, parent=None) -> None:
    from PySide6.QtWidgets import QInputDialog

    app, ok = QInputDialog.getText(
        parent,
        _("Open with"),
        _("Application name:"),
    )
    if ok and app.strip():
        subprocess.Popen(["open", "-a", app.strip(), str(path)])
    else:
        open_default(path)
