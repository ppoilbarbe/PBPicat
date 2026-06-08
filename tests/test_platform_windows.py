"""Tests for src/pbpicat/platform/_windows.py (imported directly; mocked os.startfile)."""

from unittest.mock import patch

from pbpicat.platform import _windows


def test_config_dir_uses_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = _windows.config_dir()
    assert result == tmp_path / "pbpicat"


def test_config_dir_falls_back_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(_windows.Path, "home", staticmethod(lambda: tmp_path))
    result = _windows.config_dir()
    assert result == tmp_path / "pbpicat"


def test_open_default(tmp_path):
    f = tmp_path / "test.jpg"
    f.touch()
    calls = []
    with patch("pbpicat.platform._windows.os.startfile", create=True, side_effect=lambda p: calls.append(p)):
        _windows.open_default(f)
    assert calls == [str(f)]


def test_open_with_success(tmp_path):
    f = tmp_path / "test.jpg"
    f.touch()
    calls = []
    with patch(
        "pbpicat.platform._windows.os.startfile", create=True, side_effect=lambda p, verb=None: calls.append((p, verb))
    ):
        _windows.open_with(f)
    assert calls[0] == (str(f), "openas")


def test_open_with_oserror_falls_back_to_default(tmp_path):
    f = tmp_path / "test.jpg"
    f.touch()
    calls = []

    def mock_startfile(p, verb=None):
        if verb == "openas":
            raise OSError("not supported")
        calls.append(p)

    with patch("pbpicat.platform._windows.os.startfile", create=True, side_effect=mock_startfile):
        _windows.open_with(f)
    assert calls == [str(f)]
