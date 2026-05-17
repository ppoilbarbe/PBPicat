"""Image loading helpers with Pillow fallback for formats Qt cannot handle."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap


def _pillow_to_qimage(pil_img) -> QImage:
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    w, h = pil_img.size
    data = pil_img.tobytes("raw", "RGBA")
    img = QImage(data, w, h, QImage.Format.Format_RGBA8888)
    return img.copy()


def load_qimage(path: Path, max_w: int = 0, max_h: int = 0) -> QImage:
    """Load an image as QImage, with optional scaling. Thread-safe."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if max_w > 0 and max_h > 0:
        orig = reader.size()
        if orig.isValid():
            reader.setScaledSize(orig.scaled(max_w, max_h, Qt.KeepAspectRatio))
    image = reader.read()
    if not image.isNull():
        return image

    try:
        from PIL import Image

        pil_img = Image.open(str(path))
        pil_img.load()
        if max_w > 0 and max_h > 0:
            pil_img.thumbnail((max_w, max_h), Image.LANCZOS)
        return _pillow_to_qimage(pil_img)
    except Exception:  # noqa: BLE001
        return QImage()


def load_pixmap(path: Path) -> QPixmap:
    """Load an image as QPixmap. Must be called from the main thread."""
    pix = QPixmap(str(path))
    if not pix.isNull():
        return pix

    try:
        from PIL import Image

        pil_img = Image.open(str(path))
        pil_img.load()
        img = _pillow_to_qimage(pil_img)
        if not img.isNull():
            return QPixmap.fromImage(img)
    except Exception:  # noqa: BLE001
        pass

    return QPixmap()
