"""Image loading helpers with Pillow fallback for formats Qt cannot handle."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QBuffer, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap

from pbpicat.image_ops import is_jpeg, repair_jpeg_sos

# Qt's image format plugins (qjpeg, etc.) are not safe to invoke concurrently
# from multiple threads: the thumbnail worker threads (load_qimage) and the
# GUI thread (load_pixmap, used by the image viewer) can deadlock inside
# QImageReader.read() if they decode at the same time. Serialize all Qt
# decodes behind one lock; Pillow's fallback path is unaffected since it
# never runs concurrently with a Qt decode of the same call.
_qimage_reader_lock = threading.Lock()


def _pillow_to_qimage(pil_img) -> QImage:
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    w, h = pil_img.size
    data = pil_img.tobytes("raw", "RGBA")
    img = QImage(data, w, h, QImage.Format.Format_RGBA8888)
    return img.copy()


# Qt's default (256 MiB) is sized against the *undecoded* image dimensions, before
# any setScaledSize() downscaling is applied. Large but legitimate photos (high-MP
# phone cameras, panoramas) can exceed it, causing QImageReader to reject the image
# outright ("Rejecting image as it exceeds the current allocation limit") and
# forcing a much slower, full-resolution Pillow fallback just to produce a small
# thumbnail. Raise it generously while still guarding against corrupt files
# advertising absurd dimensions.
_ALLOCATION_LIMIT_MIB = 1024


def _make_reader(path: Path) -> tuple[QImageReader, QBuffer | None]:
    """Build a QImageReader for path, repairing known-malformed JPEG headers first.

    Some camera firmware writes an invalid SOS marker that Qt merely warns
    about ("Invalid SOS parameters for sequential JPEG"); repairing it up
    front avoids the warning and the decode issues it can cause.
    """
    if is_jpeg(path):
        try:
            data = repair_jpeg_sos(path.read_bytes())
        except OSError:
            reader = QImageReader(str(path))
            reader.setAllocationLimit(_ALLOCATION_LIMIT_MIB)
            return reader, None
        buf = QBuffer()
        buf.setData(data)
        buf.open(QBuffer.OpenModeFlag.ReadOnly)
        reader = QImageReader(buf, b"jpg")
        reader.setAllocationLimit(_ALLOCATION_LIMIT_MIB)
        return reader, buf
    reader = QImageReader(str(path))
    reader.setAllocationLimit(_ALLOCATION_LIMIT_MIB)
    return reader, None


def load_qimage(path: Path, max_w: int = 0, max_h: int = 0, auto_rotate: bool = True) -> QImage:
    """Load an image as QImage, with optional scaling. Thread-safe."""
    with _qimage_reader_lock:
        reader, _buf = _make_reader(path)
        reader.setAutoTransform(auto_rotate)
        if max_w > 0 and max_h > 0:
            orig = reader.size()
            if orig.isValid():
                reader.setScaledSize(orig.scaled(max_w, max_h, Qt.KeepAspectRatio))
        image = reader.read()
    if not image.isNull():
        return image

    try:
        from PIL import Image, ImageOps

        pil_img = Image.open(str(path))
        pil_img.load()
        if auto_rotate:
            pil_img = ImageOps.exif_transpose(pil_img)
        if max_w > 0 and max_h > 0:
            pil_img.thumbnail((max_w, max_h), Image.LANCZOS)
        return _pillow_to_qimage(pil_img)
    except Exception:  # noqa: BLE001
        return QImage()


def load_pixmap(path: Path, auto_rotate: bool = True) -> QPixmap:
    """Load an image as QPixmap. Must be called from the main thread."""
    with _qimage_reader_lock:
        reader, _buf = _make_reader(path)
        reader.setAutoTransform(auto_rotate)
        image = reader.read()
    if not image.isNull():
        return QPixmap.fromImage(image)

    try:
        from PIL import Image, ImageOps

        pil_img = Image.open(str(path))
        pil_img.load()
        if auto_rotate:
            pil_img = ImageOps.exif_transpose(pil_img)
        img = _pillow_to_qimage(pil_img)
        if not img.isNull():
            return QPixmap.fromImage(img)
    except Exception:  # noqa: BLE001
        pass

    return QPixmap()
