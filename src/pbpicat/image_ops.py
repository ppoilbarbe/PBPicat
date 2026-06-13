"""Lossless image rotation. jpegtran (libjpeg-turbo) required for JPEG files."""

import shutil
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

    data = path.read_bytes()
    proc = subprocess.run(
        [exe, "-copy", "all", "-trim"] + _OP_TO_JPEGTRAN[op],
        input=data,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip())

    path.write_bytes(proc.stdout)
    if strip_exif_orientation:
        _strip_jpeg_orientation(path)


def set_exif_orientation(path: Path, value: int) -> None:
    """Set EXIF Orientation tag to value in a JPEG file in-place (requires piexif)."""
    try:
        import piexif

        exif = piexif.load(str(path))
        exif["0th"][piexif.ImageIFD.Orientation] = value
        piexif.insert(piexif.dump(exif), str(path))
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
