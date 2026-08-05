"""Lossless image rotation. jpegtran (libjpeg-turbo) required for JPEG files."""

import shutil
import struct
import subprocess
import sys
from pathlib import Path

_JPEG_EXTS = frozenset({".jpg", ".jpeg", ".jpe"})
_EXIF_ORIENTATION_TAG = 274

# EXIF orientation → op descriptor (int = degrees CW, str = flip/transform name)
_ORIENT_TO_OP: dict[int, int | str] = {
    2: "hflip",
    3: 180,
    4: "vflip",
    5: "transpose",
    6: 90,
    7: "transverse",
    8: -90,
}

# op descriptor → jpegtran argument(s)
_OP_TO_JPEGTRAN: dict[int | str, list[str]] = {
    90: ["-rotate", "90"],
    -90: ["-rotate", "270"],
    180: ["-rotate", "180"],
    "hflip": ["-flip", "horizontal"],
    "vflip": ["-flip", "vertical"],
    "transpose": ["-transpose"],
    "transverse": ["-transverse"],
}

# Inverse op (flip ops are self-inverse)
_OP_INVERSE: dict[int | str, int | str] = {
    90: -90,
    -90: 90,
    180: 180,
    "hflip": "hflip",
    "vflip": "vflip",
    "transpose": "transpose",
    "transverse": "transverse",
}


def is_jpeg(path: Path) -> bool:
    return path.suffix.lower() in _JPEG_EXTS


def repair_jpeg_sos(data: bytes) -> bytes:
    """Fix a malformed SOS header found in some camera firmware (e.g. certain
    Samsung front-camera modules): baseline (non-progressive) JPEGs must have
    Se=63 in the SOS segment, but these encoders write Se=0. Strict decoders
    (jpegtran/libjpeg-turbo) reject this with "Invalid SOS parameters for
    sequential JPEG"; lenient decoders (Qt, Pillow) just warn and decode
    anyway. Patching the header byte is lossless: no entropy-coded data is
    touched. Returns the input unchanged if no such defect is found.
    """
    if data[:2] != b"\xff\xd8":
        return data
    baseline = False
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1):
            baseline = True
        elif marker in (0xC2, 0xC3):
            baseline = False
        elif marker == 0xDA:
            if baseline:
                ns = data[i + 4]
                se_offset = i + 6 + 2 * ns
                if se_offset < n and data[se_offset] == 0 and data[se_offset - 1] == 0:
                    patched = bytearray(data)
                    patched[se_offset] = 0x3F
                    return bytes(patched)
            return data
        i += 2 + length
    return data


def get_exif_orientation(path: Path) -> int | None:
    """Return EXIF Orientation value 2–8 if present and non-trivial, else None."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            exif = img._getexif()  # noqa: SLF001
            if exif:
                val = exif.get(_EXIF_ORIENTATION_TAG)
                if val and val != 1:
                    return int(val)
    except Exception:  # noqa: BLE001
        pass
    return None


def rotate_lossless(path: Path, op: int | str) -> int | str:
    """
    Apply a lossless rotation/flip to path in-place.

    op: 90, -90, 180  (degrees CW)
        "auto"        (apply + clear EXIF orientation tag)
        "hflip" / "vflip" / "transpose" / "transverse"  (for undo of flip-type EXIF)

    Returns the inverse op for undo.

    Raises RuntimeError (user-friendly) if jpegtran is unavailable for a JPEG file.
    Raises ValueError if op == "auto" and no EXIF orientation found.
    """
    if op == "auto":
        orient = get_exif_orientation(path)
        if orient is None:
            raise ValueError(_("No EXIF orientation tag to apply."))
        actual_op = _ORIENT_TO_OP.get(orient)
        if actual_op is None:
            raise ValueError(_("Unsupported EXIF orientation value: {v}").format(v=orient))
        _apply_op(path, actual_op, strip_exif_orientation=True)
        return _OP_INVERSE[actual_op]

    _apply_op(path, op, strip_exif_orientation=True)
    return _OP_INVERSE[op]


def _apply_op(path: Path, op: int | str, strip_exif_orientation: bool = False) -> None:
    if is_jpeg(path):
        _jpeg_apply(path, op, strip_exif_orientation)
    else:
        _pil_apply(path, op)


# ---------------------------------------------------------------------------
# JPEG path (requires jpegtran from libjpeg-turbo)
# ---------------------------------------------------------------------------


def _jpegtran_error_hints() -> dict[str, str]:
    """Substrings of jpegtran's stderr mapped to a user-friendly explanation, shown
    above the raw technical message. Files hitting these are genuinely defective
    (missing or malformed data) rather than affected by a fixable quirk.
    """
    return {
        "Premature end of JPEG file": _(
            "This file appears to be truncated (data is missing at the end), "
            "likely from an incomplete write by the camera. Lossless rotation "
            "is not possible without discarding the affected rows."
        ),
    }


def _find_jpegtran() -> str | None:
    """Locate jpegtran, checking the PyInstaller bundle directory first."""
    if hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "jpegtran"  # noqa: SLF001
        if candidate.exists():
            return str(candidate)
    return shutil.which("jpegtran")


def _jpeg_apply(path: Path, op: int | str, strip_exif_orientation: bool) -> None:
    exe = _find_jpegtran()
    if not exe:
        raise RuntimeError(
            _(
                "jpegtran is not available.\n"
                "JPEG lossless rotation requires jpegtran.\n"
                "Install libjpeg-turbo to enable this feature."
            )
        )

    data = repair_jpeg_sos(path.read_bytes())
    proc = subprocess.run(
        [exe, "-copy", "all", "-trim"] + _OP_TO_JPEGTRAN[op],
        input=data,
        capture_output=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        hint = next((msg for key, msg in _jpegtran_error_hints().items() if key in detail), None)
        raise RuntimeError(f"{hint}\n\n({detail})" if hint else detail)

    path.write_bytes(proc.stdout)
    if strip_exif_orientation:
        _strip_jpeg_orientation(path)


def set_exif_orientation(path: Path, value: int) -> None:
    """Set EXIF Orientation tag to value in a JPEG file in-place (requires pyexiv2).

    No-op if the file has no EXIF block at all, matching the pre-rotation state
    (a rotated file that never had EXIF should not gain one just to hold Orientation=1).
    """
    try:
        import pyexiv2

        img = pyexiv2.Image(str(path))
        try:
            if not img.read_exif():
                return
            img.modify_exif({"Exif.Image.Orientation": str(value)})
        finally:
            img.close()
    except Exception:  # noqa: BLE001
        pass


def _strip_jpeg_orientation(path: Path) -> None:
    set_exif_orientation(path, 1)


# ---------------------------------------------------------------------------
# Non-JPEG path (PIL)
# ---------------------------------------------------------------------------

_PIL_TRANSPOSE = {
    "hflip": None,  # handled via rotate mirror
    "vflip": None,
    "transpose": "TRANSPOSE",
    "transverse": "TRANSVERSE",
}


def _pil_apply(path: Path, op: int | str) -> None:
    from PIL import Image

    with Image.open(path) as img:
        if isinstance(op, int):
            # PIL rotate: positive = CCW; our convention positive = CW → negate
            rotated = img.rotate(-op, expand=True)
        elif op == "hflip":
            rotated = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif op == "vflip":
            rotated = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif op == "transpose":
            rotated = img.transpose(Image.TRANSPOSE)
        elif op == "transverse":
            rotated = img.transpose(Image.TRANSVERSE)
        else:
            raise ValueError(f"Unknown op: {op}")
        _pil_save_lossless(rotated, path)


def _pil_save_lossless(img, path: Path) -> None:
    ext = path.suffix.lower()
    if ext == ".png":
        img.save(path, format="PNG")
    elif ext in (".tiff", ".tif"):
        img.save(path, format="TIFF", compression="none")
    elif ext == ".bmp":
        img.save(path, format="BMP")
    elif ext == ".webp":
        img.save(path, format="WEBP", lossless=True)
    else:
        img.save(path)
