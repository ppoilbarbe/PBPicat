import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

if hasattr(sys, "_MEIPASS"):
    # Used only in bundle.
    _RESOURCE_DIR = Path(sys._MEIPASS) / "resources"  # pragma: no cover — set at import time; unreachable in pytest
else:
    _RESOURCE_DIR = Path(__file__).parent.parent / "resources"
ICON_SIZE = 22

# Mapping: SVG name → FreeDesktop theme name (used when theme_name is not supplied)
_THEME_MAP = {
    "zoom-fit": "zoom-fit-best",
    "zoom-original": "zoom-original",
    "zoom-width": "zoom-fit-width",
    "zoom-height": "zoom-fit-height",
    "zoom-in": "zoom-in",
    "zoom-out": "zoom-out",
    "open": "document-open",
    "open-with": "applications-other",
    "rename-template": "view-list-details",
    "delete": "edit-delete",
}


def _text_icon(text: str, size: int = ICON_SIZE) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    f = p.font()
    f.setPixelSize(max(8, size - 6))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, text)
    p.end()
    return QIcon(pix)


def get_icon(svg_name: str, theme_name: str = "", text_fallback: str = "") -> QIcon:
    """Return an icon: system theme → SVG file → text fallback (or null QIcon)."""
    icon = QIcon.fromTheme(theme_name or _THEME_MAP.get(svg_name, ""))
    if not icon.isNull():
        return icon
    svg = _RESOURCE_DIR / f"{svg_name}.svg"
    if svg.exists():
        icon = QIcon(str(svg))
        if not icon.isNull():
            return icon
    return _text_icon(text_fallback) if text_fallback else QIcon()
