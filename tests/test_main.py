"""Tests for src/pbpicat/__main__.py."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from pbpicat.__main__ import _show_obsolete_notice as _real_show_obsolete_notice


@pytest.fixture(autouse=True)
def _no_obsolete_notice():
    """Prevent the blocking obsolescence dialog from opening during main() tests."""
    with patch("pbpicat.__main__._show_obsolete_notice"):
        yield


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
    monkeypatch.setattr("sys.argv", ["pbpicat"])
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


# --- main() ---


def test_main_module_importable():
    """Importing __main__ should not raise (covers module-level code)."""
    import importlib

    import pbpicat.__main__

    importlib.reload(pbpicat.__main__)


def test_main_dev_config_dir(tmp_path, catalog_env, monkeypatch):
    """--dev-config-dir forwards the path to set_base_dir before init_catalogs."""
    custom_dir = tmp_path / "custom_cfg"
    monkeypatch.setattr("sys.argv", ["pbpicat", f"--dev-config-dir={custom_dir}"])

    captured = {}

    def fake_set_base_dir(path):
        captured["path"] = path

    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app),
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("pbpicat.__main__.set_base_dir", side_effect=fake_set_base_dir),
        patch("sys.exit"),
    ):
        from pbpicat.__main__ import main

        main()

    assert captured["path"] == custom_dir


def test_main_catalog_arg_existing(catalog_env, monkeypatch):
    """Positional catalog arg switches to it when the catalog exists."""
    (catalog_env.parent / "work").mkdir()
    monkeypatch.setattr("sys.argv", ["pbpicat", "work"])
    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app),
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("pbpicat.__main__.set_current_catalog") as mock_set,
        patch("pbpicat.__main__.QMessageBox") as mock_box,
        patch("sys.exit"),
    ):
        from pbpicat.__main__ import main

        main()

    mock_set.assert_called_once_with("work")
    mock_box.warning.assert_not_called()


def test_main_catalog_arg_hidden(catalog_env, monkeypatch):
    """A hidden catalog name (starting with '.') is accepted."""
    (catalog_env.parent / ".secret").mkdir()
    monkeypatch.setattr("sys.argv", ["pbpicat", ".secret"])
    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app),
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("pbpicat.__main__.set_current_catalog") as mock_set,
        patch("sys.exit"),
    ):
        from pbpicat.__main__ import main

        main()

    mock_set.assert_called_once_with(".secret")


def test_main_catalog_arg_missing(catalog_env, monkeypatch):
    """An unknown catalog name shows an error and falls back to the current behaviour."""
    monkeypatch.setattr("sys.argv", ["pbpicat", "nonexistent"])
    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app),
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("pbpicat.__main__.set_current_catalog") as mock_set,
        patch("pbpicat.__main__.QMessageBox") as mock_box,
        patch("sys.exit"),
    ):
        from pbpicat.__main__ import main

        main()

    mock_set.assert_not_called()
    mock_box.warning.assert_called_once()


def test_main_passes_qt_args_to_qapplication(catalog_env, monkeypatch):
    """Qt options reach QApplication as single-dash flags."""
    monkeypatch.setattr("sys.argv", ["pbpicat", "--style", "fusion"])
    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app) as mock_qapp,
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("sys.exit"),
    ):
        from pbpicat.__main__ import main

        main()

    mock_qapp.assert_called_once_with(["pbpicat", "-style", "fusion"])


def test_show_obsolete_notice_links_to_pbrenamer():
    """The obsolescence dialog shows a clickable link to the PBRenamer releases."""
    from PySide6.QtCore import Qt

    from pbpicat import __main__ as mod

    box = MagicMock()
    # The autouse fixture replaced the module attribute; call the real function.
    with patch.object(mod, "QMessageBox", return_value=box):
        _real_show_obsolete_notice()

    box.setTextFormat.assert_called_once_with(Qt.RichText)
    text = box.setText.call_args.args[0]
    assert f'<a href="{mod.PBRENAMER_RELEASES_URL}">' in text
    assert "2.0" in text
    box.exec.assert_called_once()


def test_main_shows_obsolete_notice(catalog_env, monkeypatch):
    """main() shows the obsolescence notice at startup."""
    monkeypatch.setattr("sys.argv", ["pbpicat"])
    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    with (
        patch("pbpicat.__main__.QApplication", return_value=mock_app),
        patch("pbpicat.__main__.MainWindow"),
        patch("pbpicat.__main__.init_catalogs"),
        patch("pbpicat.__main__.i18n"),
        patch("pbpicat.__main__._show_obsolete_notice") as mock_notice,
        patch("sys.exit"),
    ):
        from pbpicat.__main__ import main

        main()

    mock_notice.assert_called_once_with()
