"""Tests for src/pbpicat/image_ops.py."""

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from pbpicat.image_ops import (
    _find_jpegtran,
    _pil_apply,
    _pil_save_lossless,
    _strip_jpeg_orientation,
    get_exif_orientation,
    is_jpeg,
    rotate_lossless,
    set_exif_orientation,
)

# MCU-aligned dimensions: no edge trimming by jpegtran
MCU_W, MCU_H = 160, 96


def _jpeg(path: Path, w: int = MCU_W, h: int = MCU_H) -> Path:
    Image.new("RGB", (w, h), color=(100, 150, 200)).save(str(path), format="JPEG")
    return path


def _jpeg_exif(path: Path, orientation: int, w: int = MCU_W, h: int = MCU_H) -> Path:
    import piexif

    img = Image.new("RGB", (w, h), color=(100, 150, 200))
    exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Orientation: orientation}})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    path.write_bytes(buf.getvalue())
    return path


def _png(path: Path, w: int = 160, h: int = 96) -> Path:
    Image.new("RGB", (w, h), color=(50, 100, 150)).save(str(path), format="PNG")
    return path


# ---------------------------------------------------------------------------
# is_jpeg
# ---------------------------------------------------------------------------


def test_is_jpeg_jpg():
    assert is_jpeg(Path("photo.jpg"))


def test_is_jpeg_jpeg():
    assert is_jpeg(Path("photo.jpeg"))


def test_is_jpeg_jpe():
    assert is_jpeg(Path("photo.jpe"))


def test_is_jpeg_uppercase():
    assert is_jpeg(Path("photo.JPG"))


def test_is_jpeg_png_false():
    assert not is_jpeg(Path("image.png"))


def test_is_jpeg_tiff_false():
    assert not is_jpeg(Path("image.tiff"))


# ---------------------------------------------------------------------------
# get_exif_orientation
# ---------------------------------------------------------------------------


def test_get_exif_orientation_no_exif(tmp_path):
    assert get_exif_orientation(_jpeg(tmp_path / "plain.jpg")) is None


def test_get_exif_orientation_trivial_1(tmp_path):
    import piexif

    img = Image.new("RGB", (MCU_W, MCU_H))
    exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 1}})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    p = tmp_path / "orient1.jpg"
    p.write_bytes(buf.getvalue())
    assert get_exif_orientation(p) is None  # value 1 = normal = ignored


def test_get_exif_orientation_value_6(tmp_path):
    assert get_exif_orientation(_jpeg_exif(tmp_path / "o6.jpg", 6)) == 6


def test_get_exif_orientation_value_3(tmp_path):
    assert get_exif_orientation(_jpeg_exif(tmp_path / "o3.jpg", 3)) == 3


def test_get_exif_orientation_png_returns_none(tmp_path):
    assert get_exif_orientation(_png(tmp_path / "img.png")) is None


def test_get_exif_orientation_nonexistent(tmp_path):
    assert get_exif_orientation(tmp_path / "nope.jpg") is None


# ---------------------------------------------------------------------------
# _find_jpegtran
# ---------------------------------------------------------------------------


def test_find_jpegtran_available():
    assert _find_jpegtran() is not None  # jpegtran in the conda env


def test_find_jpegtran_not_found():
    with patch("pbpicat.image_ops.shutil.which", return_value=None):
        # Remove _MEIPASS if present (not in a bundle)
        had = hasattr(sys, "_MEIPASS")
        if had:
            meipass = sys._MEIPASS
            del sys._MEIPASS
        try:
            assert _find_jpegtran() is None
        finally:
            if had:
                sys._MEIPASS = meipass


def test_find_jpegtran_meipass_found(tmp_path):
    fake = tmp_path / "jpegtran"
    fake.touch()
    with patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
        result = _find_jpegtran()
    assert result == str(fake)


def test_find_jpegtran_meipass_missing_falls_through(tmp_path):
    # MEIPASS set but no jpegtran in it → falls back to PATH
    with patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
        result = _find_jpegtran()
    assert result is not None  # found via PATH


# ---------------------------------------------------------------------------
# rotate_lossless — JPEG
# ---------------------------------------------------------------------------


def test_rotate_jpeg_90_cw(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, 90)
    with Image.open(p) as img:
        assert img.size == (MCU_H, MCU_W)
    assert undo == -90


def test_rotate_jpeg_90_ccw(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, -90)
    with Image.open(p) as img:
        assert img.size == (MCU_H, MCU_W)
    assert undo == 90


def test_rotate_jpeg_180(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, 180)
    with Image.open(p) as img:
        assert img.size == (MCU_W, MCU_H)
    assert undo == 180


def test_rotate_jpeg_hflip(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, "hflip")
    with Image.open(p) as img:
        assert img.size == (MCU_W, MCU_H)
    assert undo == "hflip"


def test_rotate_jpeg_vflip(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, "vflip")
    with Image.open(p) as img:
        assert img.size == (MCU_W, MCU_H)
    assert undo == "vflip"


def test_rotate_jpeg_transpose(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, "transpose")
    with Image.open(p) as img:
        assert img.size == (MCU_H, MCU_W)
    assert undo == "transpose"


def test_rotate_jpeg_transverse(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, "transverse")
    with Image.open(p) as img:
        assert img.size == (MCU_H, MCU_W)
    assert undo == "transverse"


def test_rotate_jpeg_undo_roundtrip(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    undo = rotate_lossless(p, 90)
    rotate_lossless(p, undo)
    with Image.open(p) as img:
        assert img.size == (MCU_W, MCU_H)


def test_rotate_jpeg_auto_applies_exif_orientation_6(tmp_path):
    # Orientation 6 = 90° CW: applying it should make landscape → portrait
    p = _jpeg_exif(tmp_path / "img.jpg", 6)
    assert get_exif_orientation(p) == 6
    undo = rotate_lossless(p, "auto")
    assert get_exif_orientation(p) is None  # tag stripped
    with Image.open(p) as img:
        assert img.size == (MCU_H, MCU_W)
    assert undo == -90  # inverse of 90° CW


def test_rotate_jpeg_auto_applies_exif_orientation_3(tmp_path):
    # Orientation 3 = 180°
    p = _jpeg_exif(tmp_path / "img.jpg", 3)
    undo = rotate_lossless(p, "auto")
    assert get_exif_orientation(p) is None
    with Image.open(p) as img:
        assert img.size == (MCU_W, MCU_H)
    assert undo == 180


def test_rotate_jpeg_auto_no_exif_raises_valueerror(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    with pytest.raises(ValueError):
        rotate_lossless(p, "auto")


def test_rotate_jpeg_no_jpegtran_raises_runtimeerror(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    with patch("pbpicat.image_ops._find_jpegtran", return_value=None):
        with pytest.raises(RuntimeError, match="jpegtran"):
            rotate_lossless(p, 90)


def test_rotate_jpeg_strips_exif_orientation_on_normal_rotate(tmp_path):
    # Even a plain 90° rotation must strip any existing EXIF orientation tag
    p = _jpeg_exif(tmp_path / "img.jpg", 6)
    rotate_lossless(p, 90)
    assert get_exif_orientation(p) is None


# ---------------------------------------------------------------------------
# rotate_lossless — PIL (non-JPEG)
# ---------------------------------------------------------------------------


def test_rotate_png_90_cw(tmp_path):
    p = _png(tmp_path / "img.png")
    undo = rotate_lossless(p, 90)
    with Image.open(p) as img:
        assert img.size == (96, 160)
    assert undo == -90


def test_rotate_png_90_ccw(tmp_path):
    p = _png(tmp_path / "img.png")
    undo = rotate_lossless(p, -90)
    with Image.open(p) as img:
        assert img.size == (96, 160)
    assert undo == 90


def test_rotate_png_180(tmp_path):
    p = _png(tmp_path / "img.png")
    undo = rotate_lossless(p, 180)
    with Image.open(p) as img:
        assert img.size == (160, 96)
    assert undo == 180


def test_rotate_png_hflip(tmp_path):
    p = _png(tmp_path / "img.png")
    rotate_lossless(p, "hflip")
    with Image.open(p) as img:
        assert img.size == (160, 96)


def test_rotate_png_vflip(tmp_path):
    p = _png(tmp_path / "img.png")
    rotate_lossless(p, "vflip")
    with Image.open(p) as img:
        assert img.size == (160, 96)


def test_rotate_png_transpose(tmp_path):
    p = _png(tmp_path / "img.png")
    rotate_lossless(p, "transpose")
    with Image.open(p) as img:
        assert img.size == (96, 160)


def test_rotate_png_transverse(tmp_path):
    p = _png(tmp_path / "img.png")
    rotate_lossless(p, "transverse")
    with Image.open(p) as img:
        assert img.size == (96, 160)


def test_rotate_png_undo_roundtrip(tmp_path):
    p = _png(tmp_path / "img.png")
    undo = rotate_lossless(p, 90)
    rotate_lossless(p, undo)
    with Image.open(p) as img:
        assert img.size == (160, 96)


# ---------------------------------------------------------------------------
# _strip_jpeg_orientation
# ---------------------------------------------------------------------------


def test_strip_jpeg_orientation_sets_to_1(tmp_path):
    import piexif

    p = _jpeg_exif(tmp_path / "img.jpg", 6)
    _strip_jpeg_orientation(p)
    exif = piexif.load(str(p))
    assert exif["0th"].get(piexif.ImageIFD.Orientation) == 1


def test_strip_jpeg_orientation_no_exif_is_stable(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    _strip_jpeg_orientation(p)  # must not raise
    assert p.exists()


# ---------------------------------------------------------------------------
# set_exif_orientation
# ---------------------------------------------------------------------------


def test_set_exif_orientation_patches_existing_tag(tmp_path):
    import piexif

    p = _jpeg_exif(tmp_path / "img.jpg", 1)
    set_exif_orientation(p, 6)
    exif = piexif.load(str(p))
    assert exif["0th"].get(piexif.ImageIFD.Orientation) == 6


def test_set_exif_orientation_no_exif_block_is_noop(tmp_path):
    p = _jpeg(tmp_path / "img.jpg")
    set_exif_orientation(p, 6)  # must not raise and must not corrupt the file
    from pbpicat.image_ops import get_exif_orientation

    assert get_exif_orientation(p) is None


def test_set_exif_orientation_overwrites_existing(tmp_path):
    import piexif

    p = _jpeg_exif(tmp_path / "img.jpg", 3)
    set_exif_orientation(p, 8)
    exif = piexif.load(str(p))
    assert exif["0th"].get(piexif.ImageIFD.Orientation) == 8


def test_undo_rotation_restores_exif_orientation(tmp_path):
    """Applying undo_op + restoring orig_orient must fully restore the original state."""
    import piexif

    p = _jpeg_exif(tmp_path / "img.jpg", 6)
    orig_orient = get_exif_orientation(p)
    undo_op = rotate_lossless(p, "auto")
    assert get_exif_orientation(p) is None  # cleared after rotation

    rotate_lossless(p, undo_op)
    if orig_orient is not None:
        set_exif_orientation(p, orig_orient)

    exif = piexif.load(str(p))
    assert exif["0th"].get(piexif.ImageIFD.Orientation) == 6


# ---------------------------------------------------------------------------
# rotate_lossless — auto: unsupported EXIF orientation value (line 84)
# ---------------------------------------------------------------------------


def test_rotate_auto_unsupported_exif_orientation_raises(tmp_path):
    p = _jpeg_exif(tmp_path / "img.jpg", 6)
    with patch("pbpicat.image_ops.get_exif_orientation", return_value=9):
        with pytest.raises(ValueError, match="9"):
            rotate_lossless(p, "auto")


# ---------------------------------------------------------------------------
# _jpeg_apply: jpegtran non-zero exit code (line 131)
# ---------------------------------------------------------------------------


def test_rotate_jpeg_jpegtran_failure_raises_runtimeerror(tmp_path):
    from unittest.mock import MagicMock

    p = _jpeg(tmp_path / "img.jpg")
    result = MagicMock()
    result.returncode = 1
    result.stderr = b"jpegtran: some error"
    with patch("pbpicat.image_ops.subprocess.run", return_value=result):
        with pytest.raises(RuntimeError, match="jpegtran: some error"):
            rotate_lossless(p, 90)


# ---------------------------------------------------------------------------
# set_exif_orientation: exception silenced
# ---------------------------------------------------------------------------


def test_set_exif_orientation_exception_is_silenced(tmp_path):
    import pyexiv2

    p = _jpeg_exif(tmp_path / "img.jpg", 3)
    with patch.object(pyexiv2.Image, "modify_exif", side_effect=Exception("pyexiv2 boom")):
        set_exif_orientation(p, 6)  # must not raise


# ---------------------------------------------------------------------------
# _pil_apply: unknown op (line 182)
# ---------------------------------------------------------------------------


def test_pil_apply_unknown_op_raises(tmp_path):
    p = _png(tmp_path / "img.png")
    with pytest.raises(ValueError, match="Unknown op"):
        _pil_apply(p, "flip_diagonal")


# ---------------------------------------------------------------------------
# _pil_save_lossless: TIFF, BMP, WebP, else branches (lines 190-197)
# ---------------------------------------------------------------------------


def _make_img(path: Path, fmt: str) -> Path:
    Image.new("RGB", (160, 96), color=(80, 120, 160)).save(str(path), format=fmt)
    return path


def test_rotate_tiff(tmp_path):
    p = _make_img(tmp_path / "img.tiff", "TIFF")
    rotate_lossless(p, 90)
    with Image.open(p) as img:
        assert img.size == (96, 160)


def test_rotate_tif_extension(tmp_path):
    p = _make_img(tmp_path / "img.tif", "TIFF")
    rotate_lossless(p, -90)
    with Image.open(p) as img:
        assert img.size == (96, 160)


def test_rotate_bmp(tmp_path):
    p = _make_img(tmp_path / "img.bmp", "BMP")
    rotate_lossless(p, 180)
    with Image.open(p) as img:
        assert img.size == (160, 96)


def test_rotate_webp(tmp_path):
    p = _make_img(tmp_path / "img.webp", "WEBP")
    rotate_lossless(p, 90)
    with Image.open(p) as img:
        assert img.size == (96, 160)


def test_pil_save_lossless_else_branch(tmp_path):
    p = tmp_path / "img.ppm"
    img = Image.new("RGB", (160, 96), color=(80, 120, 160))
    _pil_save_lossless(img, p)
    assert p.exists()
    with Image.open(p) as loaded:
        assert loaded.size == (160, 96)
