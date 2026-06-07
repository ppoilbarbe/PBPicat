"""Tests for src/pbpicat/__main__.py."""

import sys
from unittest.mock import MagicMock, patch


def test_resource_without_meipass():
    from pbpicat.__main__ import _resource

    result = _resource("resources/pbpicat.svg")
    # result = <pkg_dir>/resources/pbpicat.svg
    assert result.name == "pbpicat.svg"
    assert result.parent.name == "resources"


def test_resource_with_meipass(tmp_path):
    from pbpicat.__main__ import _resource

    original = getattr(sys, "_MEIPASS", None)
    sys._MEIPASS = str(tmp_path)
    try:
        result = _resource("resources/pbpicat.svg")
        assert result == tmp_path / "resources" / "pbpicat.svg"
    finally:
        if original is None:
            del sys._MEIPASS
        else:
            sys._MEIPASS = original


def test_main_runs_and_exits(catalog_env, monkeypatch):
    """main() completes without error when QApplication.exec returns 0."""
    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app),
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("sys.exit") as mock_exit,
    ):
        from pbpicat.__main__ import main

        main()
        mock_exit.assert_called_once_with(0)


def test_main_module_importable():
    """Importing __main__ should not raise (covers module-level code)."""
    import importlib

    import pbpicat.__main__

    importlib.reload(pbpicat.__main__)
