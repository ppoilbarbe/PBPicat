"""Tests for src/pbpicat/image_io.py."""

from unittest.mock import MagicMock, patch

from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from pbpicat.image_io import _pillow_to_qimage, load_pixmap, load_qimage

# ---------------------------------------------------------------------------
# _pillow_to_qimage
# ---------------------------------------------------------------------------


def test_pillow_to_qimage_rgba(qapp):
    img = Image.new("RGBA", (10, 10), (255, 0, 128, 200))
    result = _pillow_to_qimage(img)
    assert not result.isNull()
    assert result.width() == 10
    assert result.height() == 10


def test_pillow_to_qimage_rgb_converts(qapp):
    img = Image.new("RGB", (8, 6), (100, 150, 200))
    result = _pillow_to_qimage(img)
    assert not result.isNull()
    assert result.width() == 8


def test_pillow_to_qimage_palette(qapp):
    img = Image.new("P", (4, 4))
    result = _pillow_to_qimage(img)
    assert not result.isNull()


# ---------------------------------------------------------------------------
# load_qimage
# ---------------------------------------------------------------------------


def test_load_qimage_qt_succeeds(qapp, sample_png):
    img = load_qimage(sample_png)
    assert not img.isNull()
    assert img.width() == 100


def test_load_qimage_with_scale(qapp, sample_png):
    img = load_qimage(sample_png, max_w=32, max_h=32)
    assert not img.isNull()
    assert img.width() <= 32
    assert img.height() <= 32


def test_load_qimage_invalid_size_no_scale(qapp, sample_png):
    """max_w/max_h == 0 → no scaling attempted."""
    img = load_qimage(sample_png, max_w=0, max_h=0)
    assert not img.isNull()


def test_load_qimage_pillow_fallback(qapp, tmp_path):
    """QImageReader fails → falls back to Pillow."""
    f = tmp_path / "test.png"
    Image.new("RGB", (20, 20), "red").save(str(f))
    with patch("pbpicat.image_io.QImageReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.read.return_value = QImage()  # null → triggers fallback
        mock_reader.size.return_value = MagicMock(isValid=lambda: False)
        mock_reader_cls.return_value = mock_reader
        img = load_qimage(f)
    assert not img.isNull()


def test_load_qimage_pillow_fallback_with_scale(qapp, tmp_path):
    """QImageReader fails with max dims → Pillow path with thumbnail."""
    f = tmp_path / "big.png"
    Image.new("RGB", (200, 200), "blue").save(str(f))
    with patch("pbpicat.image_io.QImageReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.read.return_value = QImage()
        mock_reader.size.return_value = MagicMock(isValid=lambda: False)
        mock_reader_cls.return_value = mock_reader
        img = load_qimage(f, max_w=32, max_h=32)
    assert not img.isNull()


def test_load_qimage_both_fail(qapp, tmp_path):
    """Non-image file: both Qt and Pillow fail → returns null QImage."""
    f = tmp_path / "test.xyz"
    f.write_text("not an image")
    img = load_qimage(f)
    assert img.isNull()


def test_load_qimage_pillow_exception(qapp, tmp_path):
    """Pillow raises an exception → returns null QImage."""
    f = tmp_path / "bad.png"
    f.write_bytes(b"\x89PNG corrupted")
    with patch("pbpicat.image_io.QImageReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.read.return_value = QImage()
        mock_reader.size.return_value = MagicMock(isValid=lambda: False)
        mock_reader_cls.return_value = mock_reader
        img = load_qimage(f)
    assert img.isNull()


# ---------------------------------------------------------------------------
# load_pixmap
# ---------------------------------------------------------------------------


def test_load_pixmap_qt_succeeds(qapp, sample_png):
    pix = load_pixmap(sample_png)
    assert not pix.isNull()
    assert pix.width() == 100


def test_load_pixmap_pillow_fallback(qapp, tmp_path):
    """QPixmap fails → falls back to Pillow."""
    f = tmp_path / "test.png"
    Image.new("RGB", (15, 15), "green").save(str(f))
    with patch("pbpicat.image_io.QPixmap") as mock_pix_cls:
        null_pix = MagicMock(spec=QPixmap)
        null_pix.isNull.return_value = True
        real_pix = MagicMock(spec=QPixmap)
        real_pix.isNull.return_value = False
        mock_pix_cls.return_value = null_pix
        mock_pix_cls.fromImage.return_value = real_pix
        pix = load_pixmap(f)
    assert not pix.isNull()


def test_load_pixmap_both_fail(qapp, tmp_path):
    f = tmp_path / "test.xyz"
    f.write_text("not an image")
    pix = load_pixmap(f)
    assert pix.isNull()


def test_load_pixmap_auto_rotate_false_qt_succeeds(qapp, sample_png):
    """auto_rotate=False uses QImageReader path (lines 51-55)."""
    pix = load_pixmap(sample_png, auto_rotate=False)
    assert not pix.isNull()
    assert pix.width() == 100
