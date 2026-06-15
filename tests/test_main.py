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
