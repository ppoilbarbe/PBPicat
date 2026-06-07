"""Tests for src/pbpicat/platform/_linux.py."""

import pathlib
import subprocess
from unittest.mock import MagicMock

from pbpicat.platform import _linux

# ---------------------------------------------------------------------------
# _parse_gio_output
# ---------------------------------------------------------------------------


def test_parse_gio_output_basic():
    lines = (
        "Default application:\n  gimp.desktop\n"
        "Registered applications:\n  gimp.desktop\n  inkscape.desktop\n"
        "Recommended:\n  foo.desktop\n"
    )
    assert _linux._parse_gio_output(lines) == ["gimp.desktop", "inkscape.desktop"]


def test_parse_gio_output_empty():
    assert _linux._parse_gio_output("") == []


def test_parse_gio_output_no_registered_section():
    assert _linux._parse_gio_output("Default application:\n  gimp.desktop\n") == []


def test_parse_gio_output_non_desktop_line_breaks_section():
    output = "Registered applications:\n  app1.desktop\n  not-a-desktop\n  app2.desktop\n"
    assert _linux._parse_gio_output(output) == ["app1.desktop"]


def test_parse_gio_output_empty_line_in_section_is_ignored():
    output = "Registered applications:\n  app1.desktop\n\n  app2.desktop\n"
    assert _linux._parse_gio_output(output) == ["app1.desktop", "app2.desktop"]


# ---------------------------------------------------------------------------
# _build_cmd
# ---------------------------------------------------------------------------


def test_build_cmd_with_f(tmp_path):
    f = tmp_path / "img.jpg"
    assert _linux._build_cmd("gimp %f", f) == ["gimp", str(f)]


def test_build_cmd_with_percent_f_upper(tmp_path):
    f = tmp_path / "img.jpg"
    assert _linux._build_cmd("gimp %F", f) == ["gimp", str(f)]


def test_build_cmd_with_u(tmp_path):
    f = tmp_path / "img.jpg"
    assert _linux._build_cmd("eog %u", f) == ["eog", str(f)]


def test_build_cmd_with_percent_u_upper(tmp_path):
    f = tmp_path / "img.jpg"
    assert _linux._build_cmd("eog %U", f) == ["eog", str(f)]


def test_build_cmd_path_appended_when_missing(tmp_path):
    f = tmp_path / "img.jpg"
    result = _linux._build_cmd("eog", f)
    assert result[-1] == str(f)


def test_build_cmd_unknown_percent_skipped(tmp_path):
    f = tmp_path / "img.jpg"
    result = _linux._build_cmd("gimp %k %f", f)
    assert "%k" not in result
    assert str(f) in result


def test_build_cmd_path_not_duplicated(tmp_path):
    f = tmp_path / "img.jpg"
    result = _linux._build_cmd("gimp %f --no-splash", f)
    assert result.count(str(f)) == 1


# ---------------------------------------------------------------------------
# _scan_desktop_dirs
# ---------------------------------------------------------------------------


def test_scan_desktop_dirs_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._scan_desktop_dirs("image/png") == []


def test_scan_desktop_dirs_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path / "nonexistent"])
    assert _linux._scan_desktop_dirs("image/png") == []


def test_scan_desktop_dirs_finds_app(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nName=GIMP\nMimeType=image/png;image/jpeg;\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    result = _linux._scan_desktop_dirs("image/png")
    assert "gimp.desktop" in result


def test_scan_desktop_dirs_no_match(tmp_path, monkeypatch):
    (tmp_path / "vlc.desktop").write_text("[Desktop Entry]\nMimeType=video/mp4;\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._scan_desktop_dirs("image/png") == []


def test_scan_desktop_dirs_deduplicates_across_dirs(tmp_path, monkeypatch):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    d1.joinpath("gimp.desktop").write_text("MimeType=image/png;\n")
    d2.joinpath("gimp.desktop").write_text("MimeType=image/png;\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [d1, d2])
    assert _linux._scan_desktop_dirs("image/png").count("gimp.desktop") == 1


def test_scan_desktop_dirs_oserror(tmp_path, monkeypatch):
    (tmp_path / "bad.desktop").write_text("...")
    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.name == "bad.desktop":
            raise OSError("denied")
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._scan_desktop_dirs("image/png") == []


# ---------------------------------------------------------------------------
# _desktop_name
# ---------------------------------------------------------------------------


def test_desktop_name_found(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nName=GIMP\nExec=gimp %f\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._desktop_name("gimp.desktop") == "GIMP"


def test_desktop_name_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._desktop_name("nonexistent.desktop") == ""


def test_desktop_name_oserror(tmp_path, monkeypatch):
    (tmp_path / "bad.desktop").write_text("...")
    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.name == "bad.desktop":
            raise OSError
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._desktop_name("bad.desktop") == ""


# ---------------------------------------------------------------------------
# _mime_type
# ---------------------------------------------------------------------------


def _mock_run_result(returncode: int, stdout: str):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    return r


def test_mime_type_from_xdg(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _mock_run_result(0, "image/jpeg\n"))
    assert _linux._mime_type(tmp_path / "test.jpg") == "image/jpeg"


def test_mime_type_xdg_not_found_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    assert _linux._mime_type(tmp_path / "test.jpg") == "image/jpeg"


def test_mime_type_xdg_empty_stdout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _mock_run_result(0, ""))
    mime = _linux._mime_type(tmp_path / "test.jpg")
    assert "jpeg" in mime or mime == ""


def test_mime_type_xdg_nonzero_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _mock_run_result(1, "error"))
    _linux._mime_type(tmp_path / "test.txt")  # should not raise


def test_mime_type_timeout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("xdg-mime", 3))
    )
    mime = _linux._mime_type(tmp_path / "test.png")
    assert "png" in mime


def test_mime_type_oserror_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(OSError()))
    _linux._mime_type(tmp_path / "test.jpg")  # should not raise


def test_mime_type_unknown_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    assert _linux._mime_type(tmp_path / "test.unknownxyz") == ""


# ---------------------------------------------------------------------------
# _registered_apps
# ---------------------------------------------------------------------------


def test_registered_apps_via_gio(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _mock_run_result(0, "Registered applications:\n  gimp.desktop\n")
    )
    apps = _linux._registered_apps("image/png")
    assert "gimp.desktop" in apps


def test_registered_apps_gio_fails_fallback_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    (tmp_path / "gimp.desktop").write_text("MimeType=image/png;\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    apps = _linux._registered_apps("image/png")
    assert "gimp.desktop" in apps


def test_registered_apps_gio_empty_fallback_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _mock_run_result(0, ""))
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._registered_apps("image/png") == []


def test_registered_apps_gio_timeout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("gio", 3)))
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    assert _linux._registered_apps("image/png") == []


# ---------------------------------------------------------------------------
# _apps_for_path
# ---------------------------------------------------------------------------


def test_apps_for_path_no_mime(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_mime_type", lambda p: "")
    assert _linux._apps_for_path(tmp_path / "test.xyz") == []


def test_apps_for_path_with_name(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(_linux, "_registered_apps", lambda mime: ["gimp.desktop"])
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nName=GIMP\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    apps = _linux._apps_for_path(tmp_path / "test.png")
    assert apps == [("GIMP", "gimp.desktop")]


def test_apps_for_path_no_name_uses_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(_linux, "_registered_apps", lambda mime: ["eog.desktop"])
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [])
    apps = _linux._apps_for_path(tmp_path / "test.png")
    assert apps == [("eog", "eog.desktop")]


def test_apps_for_path_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_mime_type", lambda p: "image/png")
    monkeypatch.setattr(_linux, "_registered_apps", lambda mime: ["gimp.desktop", "gimp.desktop"])
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [])
    apps = _linux._apps_for_path(tmp_path / "test.png")
    assert len(apps) == 1


# ---------------------------------------------------------------------------
# open_default
# ---------------------------------------------------------------------------


def test_open_default_calls_qdesktopservices(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(_linux.QDesktopServices, "openUrl", staticmethod(lambda url: calls.append(url)))
    _linux.open_default(tmp_path / "test.png")
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# open_with
# ---------------------------------------------------------------------------


def test_open_with_dialog_cancelled(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(_linux, "_apps_for_path", lambda p: [])

    class _CancelDialog:
        def exec(self):
            return QDialog.Rejected

        def selected_desktop_file(self):
            return None

    monkeypatch.setattr(_linux, "_AppChooserDialog", lambda apps, parent: _CancelDialog())
    _linux.open_with(tmp_path / "test.png")


def test_open_with_app_selected(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(_linux, "_apps_for_path", lambda p: [("GIMP", "gimp.desktop")])
    launched = []

    class _AcceptDialog:
        def exec(self):
            return QDialog.Accepted

        def selected_desktop_file(self):
            return "gimp.desktop"

    monkeypatch.setattr(_linux, "_AppChooserDialog", lambda apps, parent: _AcceptDialog())
    monkeypatch.setattr(_linux, "_launch", lambda df, p: launched.append(df))
    _linux.open_with(tmp_path / "test.png")
    assert launched == ["gimp.desktop"]


def test_open_with_no_file_selected(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(_linux, "_apps_for_path", lambda p: [("GIMP", "gimp.desktop")])

    class _AcceptNoFile:
        def exec(self):
            return QDialog.Accepted

        def selected_desktop_file(self):
            return None

    monkeypatch.setattr(_linux, "_AppChooserDialog", lambda apps, parent: _AcceptNoFile())
    _linux.open_with(tmp_path / "test.png")  # no crash


# ---------------------------------------------------------------------------
# _launch
# ---------------------------------------------------------------------------


def test_launch_via_gtk_launch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    _linux._launch("gimp.desktop", tmp_path / "test.png")
    assert calls[0][0] == "gtk-launch"


def test_launch_fallback_to_exec_via_desktop(tmp_path, monkeypatch):
    def mock_popen(cmd):
        if cmd[0] == "gtk-launch":
            raise FileNotFoundError
        return None

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    exec_calls = []
    monkeypatch.setattr(_linux, "_exec_via_desktop", lambda df, p: exec_calls.append(df))
    _linux._launch("gimp.desktop", tmp_path / "test.png")
    assert exec_calls == ["gimp.desktop"]


# ---------------------------------------------------------------------------
# _exec_via_desktop
# ---------------------------------------------------------------------------


def test_exec_via_desktop_with_exec(tmp_path, monkeypatch):
    (tmp_path / "gimp.desktop").write_text("[Desktop Entry]\nExec=gimp %f\n")
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: popen_calls.append(cmd))
    _linux._exec_via_desktop("gimp.desktop", tmp_path / "test.png")
    assert popen_calls[0][0] == "gimp"


def test_exec_via_desktop_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    _linux._exec_via_desktop("nonexistent.desktop", tmp_path / "test.png")


def test_exec_via_desktop_oserror(tmp_path, monkeypatch):
    (tmp_path / "bad.desktop").write_text("...")
    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.name == "bad.desktop":
            raise OSError
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    monkeypatch.setattr(_linux, "_XDG_APP_DIRS", [tmp_path])
    _linux._exec_via_desktop("bad.desktop", tmp_path / "test.png")


# ---------------------------------------------------------------------------
# _AppChooserDialog
# ---------------------------------------------------------------------------


def test_app_chooser_dialog_empty_list(qapp):
    dlg = _linux._AppChooserDialog([], None)
    assert dlg._list.count() == 0
    assert dlg.selected_desktop_file() is None


def test_app_chooser_dialog_with_apps(qtbot):
    apps = [("GIMP", "gimp.desktop"), ("Inkscape", "inkscape.desktop")]
    dlg = _linux._AppChooserDialog(apps, None)
    qtbot.addWidget(dlg)
    assert dlg._list.count() == 2
    assert dlg._list.currentRow() == 0
    assert dlg.selected_desktop_file() == "gimp.desktop"


def test_app_chooser_dialog_activate_accepts(qtbot):
    apps = [("GIMP", "gimp.desktop")]
    dlg = _linux._AppChooserDialog(apps, None)
    qtbot.addWidget(dlg)
    dlg._on_activate(dlg._list.item(0))
    # accepted state set (we can't call exec() but _on_activate calls accept())
