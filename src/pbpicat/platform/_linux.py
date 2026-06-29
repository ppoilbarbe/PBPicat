"""Linux (XDG) file-open helpers."""

from __future__ import annotations

import mimetypes
import os
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

_XDG_APP_DIRS: list[Path] = [
    Path.home() / ".local/share/applications",
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
]

# Run subprocesses with English output to avoid locale-dependent parsing.
_C_ENV = {**os.environ, "LANG": "C", "LC_ALL": "C"}


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pbpicat"


def open_default(path: Path) -> None:
    subprocess.Popen(["xdg-open", str(path)])


def open_with(path: Path, parent=None) -> None:
    apps = _apps_for_path(path)
    dialog = _AppChooserDialog(apps, parent)
    if dialog.exec() != QDialog.Accepted:
        return
    desktop_file = dialog.selected_desktop_file()
    if desktop_file:
        _launch(desktop_file, path)


# ---------------------------------------------------------------------------
# MIME type
# ---------------------------------------------------------------------------


def _mime_type(path: Path) -> str:
    try:
        result = subprocess.run(
            ["xdg-mime", "query", "filetype", str(path)],
            capture_output=True,
            text=True,
            timeout=3,
            env=_C_ENV,
        )
        if result.returncode == 0:
            mime = result.stdout.strip()
            if mime:
                return mime
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    mime, _ = mimetypes.guess_type(str(path))
    return mime or ""


# ---------------------------------------------------------------------------
# App list
# ---------------------------------------------------------------------------


def _apps_for_path(path: Path) -> list[tuple[str, str]]:
    mime = _mime_type(path)
    desktop_files = _registered_apps(mime) if mime else []

    seen: set[str] = set()
    apps: list[tuple[str, str]] = []
    for df in desktop_files:
        if df in seen:
            continue
        seen.add(df)
        name = _desktop_name(df) or df.removesuffix(".desktop")
        apps.append((name, df))
    return apps


def _registered_apps(mime: str) -> list[str]:
    # Try gio first (LANG=C avoids locale-dependent section headers).
    try:
        result = subprocess.run(
            ["gio", "mime", mime],
            capture_output=True,
            text=True,
            timeout=3,
            env=_C_ENV,
        )
        if result.returncode == 0:
            apps = _parse_gio_output(result.stdout)
            if apps:
                return apps
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return _scan_desktop_dirs(mime)


def _parse_gio_output(output: str) -> list[str]:
    """Extract .desktop file names from 'gio mime' output."""
    apps: list[str] = []
    in_registered = False
    for line in output.splitlines():
        s = line.strip()
        if s == "Registered applications:":
            in_registered = True
        elif in_registered:
            if s.endswith(".desktop"):
                apps.append(s)
            elif s:
                break  # reached "Default application:" or next section
    return apps


def _scan_desktop_dirs(mime: str) -> list[str]:
    """Fallback: scan .desktop files for matching MimeType entry."""
    apps: list[str] = []
    seen: set[str] = set()
    for d in _XDG_APP_DIRS:
        if not d.is_dir():
            continue
        for fp in d.glob("*.desktop"):
            if fp.name in seen:
                continue
            try:
                for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("MimeType="):
                        if mime in line[9:].split(";"):
                            apps.append(fp.name)
                            seen.add(fp.name)
                        break
            except OSError:
                pass
    return apps


def _desktop_name(desktop_file: str) -> str:
    for d in _XDG_APP_DIRS:
        fp = d / desktop_file
        if not fp.is_file():
            continue
        try:
            for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Name="):
                    return line[5:].strip()
        except OSError:
            pass
    return ""


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------


def _launch(desktop_file: str, path: Path) -> None:
    try:
        subprocess.Popen(["gtk-launch", desktop_file, str(path)])
        return
    except FileNotFoundError:
        pass
    _exec_via_desktop(desktop_file, path)


def _exec_via_desktop(desktop_file: str, path: Path) -> None:
    for d in _XDG_APP_DIRS:
        fp = d / desktop_file
        if not fp.is_file():
            continue
        try:
            for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Exec="):
                    cmd = _build_cmd(line[5:].strip(), path)
                    subprocess.Popen(cmd)
                    return
        except OSError:
            pass


def _build_cmd(exec_val: str, path: Path) -> list[str]:
    parts = shlex.split(exec_val)
    result: list[str] = []
    for part in parts:
        if part in ("%f", "%F", "%u", "%U"):
            result.append(str(path))
        elif part.startswith("%"):
            pass
        else:
            result.append(part)
    if str(path) not in result:
        result.append(str(path))
    return result


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class _AppChooserDialog(QDialog):
    def __init__(self, apps: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Open with"))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Choose an application:")))

        self._list = QListWidget()
        for name, desktop_file in apps:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, desktop_file)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.itemActivated.connect(self._on_activate)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_activate(self, _item) -> None:
        self.accept()

    def selected_desktop_file(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.UserRole) if item else None
