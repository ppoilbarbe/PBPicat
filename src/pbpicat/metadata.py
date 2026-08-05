"""EXIF/IPTC/XMP metadata reading (embedded + XMP sidecar), via pyexiv2."""

from pathlib import Path

import pyexiv2

# (section title, [(tag, value), ...])
MetadataSection = tuple[str, list[tuple[str, str]]]


def _stringify(value: object) -> str:
    if isinstance(value, dict):
        # XMP lang-alt values, e.g. {'lang="x-default"': 'text'}
        return "; ".join(str(v) for v in value.values())
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _strip_family(key: str) -> str:
    """Drop the redundant leading family segment (Exif./Iptc./Xmp.) from a tag key."""
    _family, _sep, rest = key.partition(".")
    return rest or key


def _to_rows(tags: dict) -> list[tuple[str, str]]:
    return sorted((_strip_family(k), _stringify(v)) for k, v in tags.items())


def _read_tags(path: Path) -> tuple[dict, dict, dict]:
    """Read embedded EXIF/IPTC/XMP tag dicts. Empty dicts for any that fail or are absent."""
    try:
        img = pyexiv2.Image(str(path))
    except Exception:  # noqa: BLE001
        return {}, {}, {}
    try:
        exif = img.read_exif()
    except Exception:  # noqa: BLE001
        exif = {}
    try:
        iptc = img.read_iptc()
    except Exception:  # noqa: BLE001
        iptc = {}
    try:
        xmp = img.read_xmp()
    except Exception:  # noqa: BLE001
        xmp = {}
    img.close()
    return exif, iptc, xmp


def find_xmp_sidecar(path: Path, sidecar_extensions: list[str]) -> Path | None:
    """Return the image's .xmp sidecar path if one is configured and exists.

    Follows the project convention (SPEC.md): parent / (stem + ext), never with_suffix.
    """
    for ext in sidecar_extensions:
        if ext.lower() == ".xmp":
            candidate = path.parent / (path.stem + ext)
            if candidate.exists():
                return candidate
    return None


def read_metadata(path: Path, sidecar_extensions: list[str]) -> list[MetadataSection]:
    """Return non-empty (section title, rows) pairs: EXIF, IPTC, XMP, then XMP sidecar if any."""
    exif, iptc, xmp = _read_tags(path)
    sections: list[MetadataSection] = []
    if exif:
        sections.append((_("EXIF"), _to_rows(exif)))
    if iptc:
        sections.append((_("IPTC"), _to_rows(iptc)))
    if xmp:
        sections.append((_("XMP"), _to_rows(xmp)))

    sidecar = find_xmp_sidecar(path, sidecar_extensions)
    if sidecar is not None:
        _s_exif, _s_iptc, sidecar_xmp = _read_tags(sidecar)
        if sidecar_xmp:
            rows = [(_("Sidecar file"), sidecar.name), *_to_rows(sidecar_xmp)]
            sections.append((_("XMP (sidecar)"), rows))

    return sections
