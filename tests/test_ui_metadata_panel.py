"""Tests for src/pbpicat/ui/metadata_panel.py."""

import io

import piexif
from PIL import Image

from pbpicat.ui.metadata_panel import MetadataPanel, _format_size


def _jpeg_with_exif(path, make: str = "ACME"):
    img = Image.new("RGB", (20, 10), color=(10, 20, 30))
    exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Make: make}})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    path.write_bytes(buf.getvalue())
    return path


def test_format_size_bytes():
    assert _format_size(500) == "500 B"


def test_format_size_kb():
    assert _format_size(2048) == "2.0 KB"


def test_format_size_tb():
    assert _format_size(2**44) == "16.0 TB"


def test_panel_starts_empty(qapp):
    panel = MetadataPanel()
    assert panel._browser.toPlainText() == ""


def test_panel_clear_resets_html(qapp, sample_png):
    panel = MetadataPanel()
    panel.load(sample_png, [])
    assert panel._browser.toPlainText() != ""
    panel.clear()
    assert panel._browser.toPlainText() == ""


def test_panel_load_shows_file_section(qapp, sample_png):
    panel = MetadataPanel()
    panel.load(sample_png, [])
    text = panel._browser.toPlainText()
    assert "test.png" in text
    assert "100" in text and "80" in text  # dimensions from sample_png fixture


def test_panel_load_shows_exif_section(qapp, tmp_path):
    path = _jpeg_with_exif(tmp_path / "photo.jpg")
    panel = MetadataPanel()
    panel.load(path, [])
    text = panel._browser.toPlainText()
    assert "EXIF" in text
    assert "ACME" in text
