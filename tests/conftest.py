"""Shared fixtures for the PBPicat test suite."""

import builtins
import gettext
import os

# Force offscreen rendering before Qt is imported — required when DISPLAY is absent
# (CI headless, SSH without X forwarding, etc.).  Must come before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

import pbpicat.config as cfg  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def install_gettext_builtin():
    """Ensure _ is available as a Python builtin for all tests."""
    if "_" not in builtins.__dict__:
        gettext.NullTranslations().install()


@pytest.fixture
def catalog_env(tmp_path, monkeypatch):
    """Redirect all config I/O to a temporary directory."""
    catalog_dir = tmp_path / "pbpicat" / "default"
    catalog_dir.mkdir(parents=True)
    monkeypatch.setattr(cfg, "_BASE_DIR", tmp_path / "pbpicat")
    monkeypatch.setattr(cfg, "_CATALOG_CONF", tmp_path / "pbpicat" / "catalog.conf")
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", tmp_path / "pbpicat" / "global_settings.json")
    monkeypatch.setattr(cfg, "_current_catalog", "default")
    return catalog_dir


@pytest.fixture
def sample_png(tmp_path):
    """Return the path to a minimal valid PNG image."""
    from PIL import Image

    img = Image.new("RGB", (100, 80), color=(128, 64, 32))
    path = tmp_path / "test.png"
    img.save(str(path))
    return path


@pytest.fixture
def media_dir(tmp_path):
    """Return a directory populated with minimal valid PNG image and sidecar files."""
    from PIL import Image

    d = tmp_path / "media"
    d.mkdir()
    for name in ["img_001.png", "img_002.png"]:
        Image.new("RGB", (1, 1), "red").save(str(d / name))
    (d / "img_001.xmp").write_text("<metadata/>")
    (d / "orphan.xmp").write_text("<orphan/>")
    return d
