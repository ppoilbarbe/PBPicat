"""Tests for src/pbpicat/platform/_macos.py (imported directly; mocked Qt + subprocess)."""

from pbpicat.platform import _macos


def test_open_default(tmp_path, monkeypatch):
    f = tmp_path / "test.png"
    f.touch()
    calls = []
    monkeypatch.setattr(_macos.QDesktopServices, "openUrl", staticmethod(lambda url: calls.append(url)))
    _macos.open_default(f)
    assert len(calls) == 1


def test_open_with_cancel(tmp_path, monkeypatch):
    from unittest.mock import patch

    f = tmp_path / "test.png"
    f.touch()
    open_calls = []
    monkeypatch.setattr(_macos.QDesktopServices, "openUrl", staticmethod(lambda url: open_calls.append(url)))
    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("", False)):
        _macos.open_with(f)
    # Cancel (ok=False) → falls back to open_default → openUrl is called
    assert len(open_calls) == 1


def test_open_with_app(tmp_path, monkeypatch):
    from unittest.mock import patch

    f = tmp_path / "test.png"
    f.touch()
    popen_calls = []
    monkeypatch.setattr(_macos.subprocess, "Popen", lambda cmd: popen_calls.append(cmd))
    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("Preview", True)):
        _macos.open_with(f)
    assert popen_calls == [["open", "-a", "Preview", str(f)]]


def test_open_with_empty_app_falls_back(tmp_path, monkeypatch):
    from unittest.mock import patch

    f = tmp_path / "test.png"
    f.touch()
    open_calls = []
    monkeypatch.setattr(_macos.QDesktopServices, "openUrl", staticmethod(lambda url: open_calls.append(url)))
    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("   ", True)):
        _macos.open_with(f)
    assert len(open_calls) == 1
