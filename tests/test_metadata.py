"""Tests for src/pbpicat/metadata.py."""

import io
from pathlib import Path

import piexif
from PIL import Image

from pbpicat.metadata import find_xmp_sidecar, read_metadata

_XMP_SIDECAR = """<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:title>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">Hello Title</rdf:li>
    </rdf:Alt>
   </dc:title>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def _jpeg_with_exif(path: Path, make: str = "ACME") -> Path:
    img = Image.new("RGB", (20, 10), color=(10, 20, 30))
    exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Make: make}})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    path.write_bytes(buf.getvalue())
    return path


def test_read_metadata_empty_for_plain_image(sample_png):
    assert read_metadata(sample_png, []) == []


def test_read_metadata_reads_embedded_exif(tmp_path):
    path = _jpeg_with_exif(tmp_path / "photo.jpg")
    sections = read_metadata(path, [])
    assert dict(sections)["EXIF"] == [("Image.Make", "ACME")]


def test_read_metadata_unreadable_file_returns_empty(tmp_path):
    path = tmp_path / "not_an_image.txt"
    path.write_text("hello")
    assert read_metadata(path, []) == []


def test_find_xmp_sidecar_matches_stem(tmp_path):
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"")
    sidecar = tmp_path / "photo.xmp"
    sidecar.write_text(_XMP_SIDECAR)
    assert find_xmp_sidecar(image, [".xmp"]) == sidecar


def test_find_xmp_sidecar_missing_returns_none(tmp_path):
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"")
    assert find_xmp_sidecar(image, [".xmp"]) is None


def test_find_xmp_sidecar_ignores_non_xmp_extensions(tmp_path):
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"")
    (tmp_path / "photo.pp3").write_text("not xmp")
    assert find_xmp_sidecar(image, [".pp3"]) is None


def test_read_metadata_includes_sidecar_xmp(tmp_path):
    image = _jpeg_with_exif(tmp_path / "photo.jpg")
    (tmp_path / "photo.xmp").write_text(_XMP_SIDECAR)

    sections = read_metadata(image, [".xmp"])

    titles = [title for title, _rows in sections]
    assert "EXIF" in titles
    sidecar_rows = dict(sections)["XMP (sidecar)"]
    assert sidecar_rows[0] == ("Sidecar file", "photo.xmp")
    assert any(k == "dc.title" for k, _v in sidecar_rows[1:])
