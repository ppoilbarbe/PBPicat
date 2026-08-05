"""Side panel showing EXIF/IPTC/XMP metadata for the currently displayed image."""

import html
from pathlib import Path

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from pbpicat import metadata
from pbpicat.image_io import image_size

_STYLE = (
    "<style>"
    "body{font-family:sans-serif;margin:0;padding:8px;font-size:9pt;}"
    "h3{color:#4a7ab5;font-size:10pt;margin:12px 0 4px 0;"
    "border-bottom:1px solid #aac;padding-bottom:2px;}"
    "h3:first-child{margin-top:0;}"
    "table{border-collapse:collapse;width:100%;margin-bottom:4px;}"
    "td{padding:2px 6px;vertical-align:top;word-break:break-word;}"
    "td:first-child{font-family:monospace;color:#444;white-space:nowrap;}"
    "tr:nth-child(even){background:#f0f4f8;}"
    "</style>"
)


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _row(key: str, value: str) -> str:
    return f"<tr><td>{html.escape(key)}</td><td>{html.escape(value)}</td></tr>"


def _section(title: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(_row(k, v) for k, v in rows)
    return f"<h3>{html.escape(title)}</h3><table>{body}</table>"


def _build_html(path: Path, sidecar_extensions: list[str]) -> str:
    file_rows = [(_("Name"), path.name)]
    try:
        file_rows.append((_("Size"), _format_size(path.stat().st_size)))
    except OSError:
        pass
    size = image_size(path)
    if size is not None:
        file_rows.append((_("Dimensions"), f"{size.width()}×{size.height()}"))

    sections = [_section(_("File"), file_rows)]
    sections += [_section(title, rows) for title, rows in metadata.read_metadata(path, sidecar_extensions)]

    return f"<html><head>{_STYLE}</head><body>{''.join(sections)}</body></html>"


class MetadataPanel(QWidget):
    """Read-only side panel rendering EXIF/IPTC/XMP metadata as HTML.

    load() does the actual (synchronous) metadata read — callers are responsible
    for only invoking it while the panel is visible, so hidden panels stay free.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setOpenExternalLinks(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)
        self.clear()

    def clear(self) -> None:
        self._browser.setHtml("")

    def load(self, path: Path, sidecar_extensions: list[str]) -> None:
        self._browser.setHtml(_build_html(path, sidecar_extensions))
