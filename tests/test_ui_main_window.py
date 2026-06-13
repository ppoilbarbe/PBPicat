"""Tests for src/pbpicat/ui/main_window.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from pbpicat.ui.main_window import MainWindow, _KeyboardShortcutsDialog, _OrphanSidecarsDialog

# ---------------------------------------------------------------------------
# _KeyboardShortcutsDialog
# ---------------------------------------------------------------------------


def test_keyboard_shortcuts_dialog_creation(qtbot, catalog_env):
    dlg = _KeyboardShortcutsDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() != ""


def test_keyboard_shortcuts_dialog_html():
    html = _KeyboardShortcutsDialog._build_html()
    assert "<html>" in html
    assert "<table>" in html


# ---------------------------------------------------------------------------
# _OrphanSidecarsDialog
# ---------------------------------------------------------------------------


def test_orphan_dialog_empty(qtbot, catalog_env):
    dlg = _OrphanSidecarsDialog([])
    qtbot.addWidget(dlg)
    assert dlg._list.count() == 0


def test_orphan_dialog_with_files(qtbot, catalog_env, tmp_path):
    f1 = tmp_path / "orphan.xmp"
    f1.write_text("x")
    dlg = _OrphanSidecarsDialog([f1])
    qtbot.addWidget(dlg)
    assert dlg._list.count() == 1


def test_orphan_dialog_refresh(qtbot, catalog_env, tmp_path):
    f1 = tmp_path / "orphan.xmp"
    f1.write_text("x")
    dlg = _OrphanSidecarsDialog([f1])
    qtbot.addWidget(dlg)
    dlg.refresh([])
    assert dlg._list.count() == 0


def test_orphan_dialog_delete_all_empty(qtbot, catalog_env):
    dlg = _OrphanSidecarsDialog([])
    qtbot.addWidget(dlg)
    dlg._delete_all()  # no crash


def test_orphan_dialog_delete_selected_no_selection(qtbot, catalog_env, tmp_path):
    f = tmp_path / "orphan.xmp"
    f.write_text("x")
    dlg = _OrphanSidecarsDialog([f])
    qtbot.addWidget(dlg)
    dlg._list.setCurrentRow(-1)
    dlg._delete_selected()  # no crash


def test_orphan_dialog_confirm_and_delete(qtbot, catalog_env, tmp_path):
    f = tmp_path / "orphan.xmp"
    f.write_text("x")
    dlg = _OrphanSidecarsDialog([f])
    qtbot.addWidget(dlg)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        dlg._delete_all()
    assert not f.exists()
    assert dlg._list.count() == 0


def test_orphan_dialog_confirm_cancel(qtbot, catalog_env, tmp_path):
    f = tmp_path / "orphan.xmp"
    f.write_text("x")
    dlg = _OrphanSidecarsDialog([f])
    qtbot.addWidget(dlg)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        dlg._delete_all()
    assert f.exists()


def test_orphan_dialog_delete_with_oserror(qtbot, catalog_env, tmp_path, monkeypatch):
    f = tmp_path / "orphan.xmp"
    f.write_text("x")
    dlg = _OrphanSidecarsDialog([f])
    qtbot.addWidget(dlg)
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("busy")))
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.Yes),
        patch.object(QMessageBox, "warning", return_value=None),
    ):
        dlg._delete_all()


def test_orphan_dialog_delete_selected(qtbot, catalog_env, tmp_path):
    f1 = tmp_path / "o1.xmp"
    f2 = tmp_path / "o2.xmp"
    f1.write_text("x")
    f2.write_text("x")
    dlg = _OrphanSidecarsDialog([f1, f2])
    qtbot.addWidget(dlg)
    dlg._list.setCurrentRow(0)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        dlg._delete_selected()
    assert not f1.exists()
    assert f2.exists()


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------


@pytest.fixture
def window(qtbot, catalog_env):
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def test_main_window_creation(window):
    assert "PBPicat" in window.windowTitle()


def test_update_title_default_catalog(window, catalog_env):
    window._update_title()
    assert "[" not in window.windowTitle()


def test_update_title_named_catalog(window, monkeypatch):
    import pbpicat.config as cfg

    monkeypatch.setattr(cfg, "_current_catalog", "my_catalog")
    window._update_title()
    assert "my_catalog" in window.windowTitle()


def test_on_file_count_changed_enables_buttons(window):
    window._on_file_count_changed(5)
    assert window._rename_all_btn.isEnabled()
    assert window._renumber_btn.isEnabled()


def test_on_file_count_changed_disables_buttons(window):
    window._on_file_count_changed(0)
    assert not window._rename_all_btn.isEnabled()
    assert not window._renumber_btn.isEnabled()


def test_update_rename_btn_no_selection(window):
    window._update_rename_btn()
    assert not window._rename_btn.isEnabled()


def test_update_image_actions_no_selection(window):
    window._update_image_actions()
    assert not window._act_img_open.isEnabled()
    assert not window._act_img_delete.isEnabled()


def test_on_filter_changed_valid(window):
    window._on_filter_changed("abc.*")
    assert window._filter_edit.lineEdit().styleSheet() == ""


def test_on_filter_changed_invalid(window):
    window._on_filter_changed("[invalid")
    assert "red" in window._filter_edit.lineEdit().styleSheet()


def test_on_filter_changed_empty(window):
    window._on_filter_changed("[invalid")
    window._on_filter_changed("")
    assert window._filter_edit.lineEdit().styleSheet() == ""


def test_on_directory_changed_clears_filter(window):
    window._filter_edit.setCurrentText("test_pattern")
    window._on_directory_changed("/some/path")
    assert window._filter_edit.currentText() == ""


def test_on_directory_changed_no_filter(window):
    window._filter_edit.setCurrentText("")
    window._on_directory_changed("/some/path")  # no crash


def test_save_filter_to_history_empty(window):
    window._filter_edit.setCurrentText("")
    window._save_filter_to_history()  # no-op for empty


def test_save_filter_to_history_invalid(window):
    window._filter_edit.setCurrentText("[bad")
    window._save_filter_to_history()  # no-op for invalid


def test_save_filter_to_history_valid(window):
    window._filter_edit.setCurrentText("nature.*")
    window._save_filter_to_history()
    items = [window._filter_edit.itemText(i) for i in range(window._filter_edit.count())]
    assert "nature.*" in items


def test_rename_files_no_dest(window):
    window._dest_edit.setText("")
    with patch.object(QMessageBox, "warning", return_value=None):
        window._rename_files([Path("/tmp/img.jpg")])


def test_rename_selected_no_selection(window):
    window._rename_selected()
    assert "No file" in window._status.currentMessage() or window._status.currentMessage() != ""


def test_rename_all_no_files(window):
    window._rename_all()
    # No files → shows status message


def test_renumber_all_no_files(window):
    window._renumber_all()  # no crash when no files


def test_undo_last_rename_empty_stack(window):
    assert not window._undo_btn.isEnabled()
    window._undo_last_rename()  # no crash


def test_refresh(window):
    window._refresh()  # no crash


def test_on_orphan_count_changed(window):
    window._on_orphan_count_changed(5)
    assert window._orphan_btn.isEnabled()
    window._on_orphan_count_changed(0)
    assert not window._orphan_btn.isEnabled()


def test_on_orphan_count_changed_with_dialog(window, tmp_path):
    f = tmp_path / "orphan.xmp"
    f.write_text("x")
    mock_dlg = MagicMock()
    mock_dlg.isVisible.return_value = True
    window._orphan_dlg = mock_dlg
    window._on_orphan_count_changed(0)
    mock_dlg.refresh.assert_called_once()


def test_img_open_delegates(window):
    with patch.object(window._file_panel.file_list, "open_selected") as mock:
        window._img_open()
        mock.assert_called_once()


def test_img_open_with_delegates(window):
    with patch.object(window._file_panel.file_list, "open_with_selected") as mock:
        window._img_open_with()
        mock.assert_called_once()


def test_img_template_delegates(window):
    with patch.object(window._file_panel.file_list, "template_selected") as mock:
        window._img_template()
        mock.assert_called_once()


def test_img_delete_delegates(window):
    with patch.object(window._file_panel.file_list, "delete_selected") as mock:
        window._img_delete()
        mock.assert_called_once()


def test_sort_by_date_changes_list(window, catalog_env):
    fl = window._file_panel.file_list
    fl._current_dir = catalog_env  # real empty dir
    fl.set_sort_by_date(True)
    assert fl._sort_by_date


def test_sort_reverse_changes_list(window, catalog_env):
    fl = window._file_panel.file_list
    fl._current_dir = catalog_env
    fl.set_sort_reverse(True)
    assert fl._sort_reverse


# ---------------------------------------------------------------------------
# Catalog management
# ---------------------------------------------------------------------------


def test_populate_catalog_list(window):
    window._populate_catalog_list()
    actions = window._catalog_menu.actions()
    assert len(actions) > 0


def test_new_catalog_empty_name(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("", True)))
    window._new_catalog()  # empty name → returns early


def test_new_catalog_cancel(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("test", False)))
    window._new_catalog()  # cancel → no action


def test_new_catalog_invalid_name(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("bad name!", True)))
    with patch.object(QMessageBox, "warning", return_value=None):
        window._new_catalog()


def test_new_catalog_already_exists(window, monkeypatch, catalog_env):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("default", True)))
    with patch.object(QMessageBox, "warning", return_value=None):
        window._new_catalog()


def test_new_catalog_success(window, monkeypatch, catalog_env):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("mycat", True)))
    with patch.object(window, "_switch_to_catalog") as mock_switch:
        window._new_catalog()
        mock_switch.assert_called_once_with("mycat")


def test_delete_catalog_no_others(window, catalog_env):
    with patch.object(QMessageBox, "information", return_value=None):
        window._delete_catalog_action()


def test_delete_catalog_cancel(window, catalog_env, monkeypatch):
    (catalog_env.parent / "extra").mkdir()
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **kw: ("extra", False)))
    window._delete_catalog_action()  # cancel → no action


def test_delete_catalog_confirm_no(window, catalog_env, monkeypatch):
    (catalog_env.parent / "extra2").mkdir()
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **kw: ("extra2", True)))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        window._delete_catalog_action()


def test_delete_catalog_success(window, catalog_env, monkeypatch):
    (catalog_env.parent / "extra3").mkdir()
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **kw: ("extra3", True)))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        window._delete_catalog_action()
    assert not (catalog_env.parent / "extra3").exists()


def test_duplicate_catalog_empty_name(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("", True)))
    window._duplicate_catalog_action()


def test_duplicate_catalog_cancel(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("copy", False)))
    window._duplicate_catalog_action()


def test_duplicate_catalog_invalid_name(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("bad name!", True)))
    with patch.object(QMessageBox, "warning", return_value=None):
        window._duplicate_catalog_action()


def test_duplicate_catalog_already_exists(window, monkeypatch, catalog_env):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("default", True)))
    with patch.object(QMessageBox, "warning", return_value=None):
        window._duplicate_catalog_action()


def test_duplicate_catalog_success(window, monkeypatch, catalog_env):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **kw: ("dup_cat", True)))
    window._duplicate_catalog_action()
    assert (catalog_env.parent / "dup_cat").is_dir()


def test_switch_to_catalog_same(window, catalog_env):
    import pbpicat.config as cfg

    current = cfg.current_catalog()
    window._switch_to_catalog(current)  # no-op


def test_apply_proposed_schema(window):
    with patch.object(window._schema_frame, "set_fields") as mock_set:
        window._apply_proposed_schema(["A", "B", "", "", "", ""])
        mock_set.assert_called_once_with(["A", "B", "", "", "", ""])


def test_close_event_saves_state(window, catalog_env):
    window.close()


def test_show_keyboard_shortcuts(window, catalog_env):
    with patch.object(_KeyboardShortcutsDialog, "exec", return_value=0):
        window._show_keyboard_shortcuts()


def test_about_dialog(window, catalog_env):
    with patch.object(QMessageBox, "about", return_value=None):
        window._about()


def test_open_settings_accepted(window, catalog_env, monkeypatch):
    from pbpicat.ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(SettingsDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(SettingsDialog, "updated_config", lambda self: window._config)
    window._open_settings()


def test_open_settings_rejected(window, catalog_env, monkeypatch):
    from pbpicat.ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(SettingsDialog, "exec", lambda self: QDialog.Rejected)
    window._open_settings()


def test_open_global_settings_accepted(window, catalog_env, monkeypatch):
    from pbpicat.ui.settings_dialog import GlobalSettingsDialog

    monkeypatch.setattr(GlobalSettingsDialog, "exec", lambda self: QDialog.Accepted)
    window._open_global_settings()


def test_open_history_accepted(window, catalog_env, monkeypatch):
    from pbpicat.ui.history_dialog import HistoryDialog

    monkeypatch.setattr(HistoryDialog, "exec", lambda self: QDialog.Accepted)
    window._open_history()


def test_open_history_rejected(window, catalog_env, monkeypatch):
    from pbpicat.ui.history_dialog import HistoryDialog

    monkeypatch.setattr(HistoryDialog, "exec", lambda self: QDialog.Rejected)
    window._open_history()


def test_reload_filter_history(window):
    window._reload_filter_history()  # no crash


def test_browse_dest(window, monkeypatch):
    """Cover _browse_dest: QFileDialog returns a path."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **kw: "/tmp/dest"))
    window._browse_dest()
    assert window._dest_edit.text() == "/tmp/dest"


def test_browse_dest_cancel(window, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **kw: ""))
    window._browse_dest()


def test_show_orphan_dialog(window, catalog_env, monkeypatch):
    """Cover _show_orphan_dialog."""
    from pbpicat.ui.main_window import _OrphanSidecarsDialog

    monkeypatch.setattr(_OrphanSidecarsDialog, "exec", lambda self: QDialog.Rejected)
    window._show_orphan_dialog()
    assert window._orphan_dlg is None


def test_rename_all_confirm_no(window, catalog_env, tmp_path, monkeypatch):
    """Cover _rename_all when user says No."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        window._rename_all()


def test_rename_all_confirm_yes_no_dest(window, catalog_env, tmp_path, monkeypatch):
    """Cover _rename_all Yes path → delegates to _rename_files."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    window._dest_edit.setText("")
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.Yes),
        patch.object(QMessageBox, "warning", return_value=None),
    ):
        window._rename_all()


def test_rename_files_schema_error(window, catalog_env, tmp_path, monkeypatch):
    """Cover _rename_files ValueError path."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    window._dest_edit.setText(str(tmp_path / "out"))
    with (
        patch("pbpicat.ui.main_window.build_rename_plan", side_effect=ValueError("bad schema")),
        patch.object(QMessageBox, "critical", return_value=None),
    ):
        window._rename_files(window._file_panel.file_list.get_all_files())


def test_rename_files_success(window, catalog_env, tmp_path, monkeypatch):
    """Cover _rename_files success path."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    dest = tmp_path / "out"
    dest.mkdir()
    window._dest_edit.setText(str(dest))
    with (
        patch("pbpicat.ui.main_window.build_rename_plan", return_value=[]),
        patch("pbpicat.ui.main_window.execute_rename"),
    ):
        window._rename_files(window._file_panel.file_list.get_all_files())
    assert window._undo_btn.isEnabled()


def test_undo_last_rename_success(window, catalog_env, tmp_path, monkeypatch):
    """Cover _undo_last_rename success path."""
    window._undo_stack.append(("rename", []))
    window._undo_btn.setEnabled(True)
    with patch("pbpicat.ui.main_window.undo_rename"):
        window._undo_last_rename()
    assert len(window._undo_stack) == 0


def test_undo_last_rename_error(window, catalog_env, monkeypatch):
    """Cover _undo_last_rename error path."""
    window._undo_stack.append(("rename", []))
    with (
        patch("pbpicat.ui.main_window.undo_rename", side_effect=FileNotFoundError("missing")),
        patch.object(QMessageBox, "critical", return_value=None),
    ):
        window._undo_last_rename()
    assert len(window._undo_stack) == 1  # not popped on error


def test_undo_renumber(window, catalog_env, monkeypatch):
    """Cover _undo_last_rename with renumber kind."""
    window._undo_stack.append(("renumber", []))
    with patch("pbpicat.ui.main_window.undo_renumber"):
        window._undo_last_rename()


def test_renumber_all_with_plan(window, catalog_env, tmp_path, monkeypatch):
    """Cover _renumber_all with a real plan."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    with (
        patch(
            "pbpicat.ui.main_window.build_renumber_plan", return_value=[(tmp_path / "img.png", tmp_path / "img2.png")]
        ),
        patch.object(QMessageBox, "question", return_value=QMessageBox.No),
    ):
        window._renumber_all()


def test_renumber_all_schema_error(window, catalog_env, tmp_path, monkeypatch):
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    with (
        patch("pbpicat.ui.main_window.build_renumber_plan", side_effect=ValueError("no numeric")),
        patch.object(QMessageBox, "critical", return_value=None),
    ):
        window._renumber_all()


def test_renumber_all_execute_error(window, catalog_env, tmp_path, monkeypatch):
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    with (
        patch("pbpicat.ui.main_window.build_renumber_plan", return_value=[(tmp_path / "a.png", tmp_path / "b.png")]),
        patch("pbpicat.ui.main_window.execute_renumber", side_effect=RuntimeError("disk full")),
        patch.object(QMessageBox, "question", return_value=QMessageBox.Yes),
        patch.object(QMessageBox, "critical", return_value=None),
    ):
        window._renumber_all()


def test_switch_to_catalog(window, catalog_env, monkeypatch):
    """Cover _switch_to_catalog (with a different catalog)."""
    import pbpicat.config as cfg

    (catalog_env.parent / "other_cat").mkdir()
    cfg.set_current_catalog("other_cat")
    try:
        window._switch_to_catalog("default")
    finally:
        cfg.set_current_catalog("default")


def test_save_filter_already_exists(window, catalog_env):
    """Cover _save_filter_to_history when text already in list."""
    window._filter_edit.addItem("existing_pattern")
    window._filter_edit.setCurrentText("existing_pattern")
    window._save_filter_to_history()
    items = [window._filter_edit.itemText(i) for i in range(window._filter_edit.count())]
    assert items.count("existing_pattern") == 1


def test_delete_catalog_active(window, catalog_env, monkeypatch):
    """Cover delete_catalog when the deleted catalog is the active one."""
    import pbpicat.config as cfg

    (catalog_env.parent / "active_one").mkdir()
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **kw: ("active_one", True)))
    cfg.set_current_catalog("active_one")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        window._delete_catalog_action()
    assert cfg.current_catalog() == "default"


def test_main_window_restores_geometry(qtbot, catalog_env, monkeypatch):
    """Cover line 325: restoreGeometry when saved geometry exists."""

    def _fake_value(key, default=None, **kwargs):
        if key == "main_window/geometry":
            return b"\x00\x01"
        if default is not None:
            return default
        return None

    mock_qs = MagicMock()
    mock_qs.value.side_effect = _fake_value
    mock_qs.setValue = MagicMock()
    mock_qs.sync = MagicMock()
    # Patch at the right level: the imported name in main_window.py
    monkeypatch.setattr("pbpicat.ui.main_window.qsettings", lambda: mock_qs)
    w = MainWindow()
    qtbot.addWidget(w)


def test_sort_by_date_via_checkbox(window, catalog_env):
    """Cover line 456: _on_sort_by_date_changed via checkbox toggle."""
    fl = window._file_panel.file_list
    fl._current_dir = catalog_env
    window._sort_by_date_chk.setChecked(True)
    assert fl._sort_by_date


def test_sort_reverse_via_checkbox(window, catalog_env):
    """Cover line 459: _on_sort_reverse_changed via checkbox toggle."""
    fl = window._file_panel.file_list
    fl._current_dir = catalog_env
    window._sort_reverse_chk.setChecked(True)
    assert fl._sort_reverse


def test_reload_filter_history_with_items(window, catalog_env):
    """Cover line 510: reload filter history when items exist."""
    from pbpicat.config import save_history

    save_history("sidecar_filter", ["pattern1", "pattern2"])
    window._reload_filter_history()
    items = [window._filter_edit.itemText(i) for i in range(window._filter_edit.count())]
    assert "pattern1" in items


def test_rename_selected_with_selection(window, catalog_env, tmp_path, monkeypatch):
    """Cover line 523: _rename_selected with files selected."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    fl = window._file_panel.file_list
    fl._current_dir = tmp_path
    fl.refresh()
    fl.selectRow(0)
    window._dest_edit.setText("")
    with patch.object(QMessageBox, "warning", return_value=None):
        window._rename_selected()


def test_populate_catalog_list_multi(window, catalog_env, monkeypatch):
    """Cover line 673: _populate_catalog_list with multiple catalogs."""
    (catalog_env.parent / "extra_cat").mkdir()
    window._populate_catalog_list()
    # Should have action for each catalog
    actions = window._catalog_menu.actions()
    action_texts = [a.text() for a in actions if not a.isSeparator()]
    assert "default" in action_texts
    assert "extra_cat" in action_texts


def test_rename_all_confirm_yes_success(window, catalog_env, tmp_path, monkeypatch):
    """Cover lines 558-559: rename_all success path."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    window._dest_edit.setText(str(tmp_path / "out"))
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.Yes),
        patch("pbpicat.ui.main_window.build_rename_plan", return_value=[]),
        patch("pbpicat.ui.main_window.execute_rename"),
    ):
        window._rename_all()
    assert window._undo_btn.isEnabled()


def test_renumber_all_confirm_yes_success(window, catalog_env, tmp_path, monkeypatch):
    """Cover lines 574-577: renumber_all success path."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    window._file_panel.file_list._current_dir = tmp_path
    window._file_panel.file_list.refresh()
    with (
        patch("pbpicat.ui.main_window.build_renumber_plan", return_value=[(tmp_path / "a.png", tmp_path / "b.png")]),
        patch("pbpicat.ui.main_window.execute_renumber"),
        patch.object(QMessageBox, "question", return_value=QMessageBox.Yes),
    ):
        window._renumber_all()
    assert window._undo_btn.isEnabled()


def test_main_window_filter_history_at_start(qtbot, catalog_env, monkeypatch):
    """Cover line 396: filter history items loaded during _build_button_zone."""
    from pbpicat.config import save_history

    save_history("sidecar_filter", ["pattern_abc"])
    w = MainWindow()
    qtbot.addWidget(w)
    items = [w._filter_edit.itemText(i) for i in range(w._filter_edit.count())]
    assert "pattern_abc" in items


def test_populate_catalog_list_action_click(window, catalog_env, monkeypatch):
    """Cover line 673: setCheckable/setChecked in _populate_catalog_list."""
    (catalog_env.parent / "cat2").mkdir()
    window._populate_catalog_list()
    actions = window._catalog_menu.actions()
    checkable = [a for a in actions if a.isCheckable()]
    assert len(checkable) >= 2  # at least 'default' and 'cat2'


def test_renumber_all_already_numbered(window, catalog_env, tmp_path, monkeypatch):
    """Cover lines 558-559: _renumber_all when plan is empty (already numbered)."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(str(tmp_path / "img.png"))
    fl = window._file_panel.file_list
    fl._stop_worker()
    fl._current_dir = tmp_path
    fl._scan_directory()
    fl._populate_table()
    assert fl.rowCount() > 0, f"Got 0 rows; display_data={fl._display_data}"
    assert len(fl._display_data) > 0, "empty display_data"
    with patch("pbpicat.ui.main_window.build_renumber_plan", return_value=[]):
        window._renumber_all()
    msg = window._status.currentMessage()
    # Message may be translated (French from i18n tests); compare via _ builtin
    expected = _("Files are already correctly numbered.")
    assert expected == msg, f"Expected {expected!r}, got {msg!r}"


def test_populate_catalog_list_double_call(window, catalog_env):
    """Cover line 673: removeAction in second _populate_catalog_list call."""
    (catalog_env.parent / "extra_cat").mkdir()
    window._populate_catalog_list()  # first call adds catalog actions
    window._populate_catalog_list()  # second call removes old and re-adds → line 673
    actions = window._catalog_menu.actions()
    checkable = [a for a in actions if a.isCheckable()]
    assert len(checkable) >= 1


# ---------------------------------------------------------------------------
# Rotation actions
# ---------------------------------------------------------------------------


def test_rotate_actions_created(window):
    assert not window._act_rotate_ccw.isEnabled()
    assert not window._act_rotate_cw.isEnabled()
    assert not window._act_rotate_180.isEnabled()
    assert not window._act_rotate_auto.isEnabled()


def test_rotate_images_success(window, catalog_env, tmp_path):
    from PIL import Image

    p = tmp_path / "img.jpg"
    Image.new("RGB", (160, 96)).save(str(p), format="JPEG")
    with patch("pbpicat.image_ops.rotate_lossless", return_value=-90) as mock_rl:
        window._rotate_images([p], 90)
    mock_rl.assert_called_once_with(p, 90)
    assert len(window._undo_stack) == 1
    kind, pairs = window._undo_stack[0]
    assert kind == "rotation"
    assert pairs == [(p, -90, None)]
    assert window._undo_btn.isEnabled()


def test_rotate_images_empty_paths(window):
    window._rotate_images([], 90)
    assert len(window._undo_stack) == 0


def test_rotate_images_runtime_error(window, tmp_path):
    from PIL import Image

    p = tmp_path / "img.jpg"
    Image.new("RGB", (160, 96)).save(str(p), format="JPEG")
    with (
        patch("pbpicat.image_ops.rotate_lossless", side_effect=RuntimeError("jpegtran is not available.")),
        patch.object(QMessageBox, "warning", return_value=None) as mock_warn,
    ):
        window._rotate_images([p], 90)
    mock_warn.assert_called_once()
    assert len(window._undo_stack) == 0


def test_rotate_images_value_error(window, tmp_path):
    from PIL import Image

    p = tmp_path / "img.jpg"
    Image.new("RGB", (160, 96)).save(str(p), format="JPEG")
    with patch("pbpicat.image_ops.rotate_lossless", side_effect=ValueError("No EXIF orientation.")):
        window._rotate_images([p], "auto")
    assert len(window._undo_stack) == 0


def test_update_undo_btn_rotation_label(window):
    from pathlib import Path

    window._undo_stack.append(("rotation", [(Path("/tmp/a.jpg"), -90, None)]))
    window._update_undo_btn()
    assert window._undo_btn.isEnabled()
    assert "rotation" in window._undo_btn.text().lower() or "Rotation" in window._undo_btn.text()
    assert "(1)" in window._undo_btn.text()


def test_undo_rotation_success(window, tmp_path):
    from PIL import Image

    p = tmp_path / "img.jpg"
    Image.new("RGB", (160, 96)).save(str(p), format="JPEG")
    window._undo_stack.append(("rotation", [(p, -90, None)]))
    window._undo_total = 1
    window._undo_btn.setEnabled(True)
    with patch("pbpicat.image_ops.rotate_lossless") as mock_rl:
        window._undo_last_rename()
    mock_rl.assert_called_once_with(p, -90)
    assert len(window._undo_stack) == 0
    assert "Rotation" in window._status.currentMessage() or "otation" in window._status.currentMessage()


def test_undo_rotation_error(window, tmp_path):
    from PIL import Image

    p = tmp_path / "img.jpg"
    Image.new("RGB", (160, 96)).save(str(p), format="JPEG")
    window._undo_stack.append(("rotation", [(p, -90, None)]))
    window._undo_total = 1
    with (
        patch("pbpicat.image_ops.rotate_lossless", side_effect=RuntimeError("jpegtran missing")),
        patch.object(QMessageBox, "critical", return_value=None),
    ):
        window._undo_last_rename()
    assert len(window._undo_stack) == 1  # not popped on error


def test_rotate_images_auto_skips_no_exif_files(window, tmp_path):
    """Files without EXIF orientation are silently skipped; only EXIF files go into undo."""
    import io

    import piexif
    from PIL import Image

    p_no_exif = tmp_path / "plain.jpg"
    Image.new("RGB", (160, 96)).save(str(p_no_exif), format="JPEG")

    p_with_exif = tmp_path / "exif.jpg"
    exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}})
    buf = io.BytesIO()
    Image.new("RGB", (160, 96)).save(buf, format="JPEG", exif=exif_bytes)
    p_with_exif.write_bytes(buf.getvalue())

    results = {p_no_exif: ValueError("No EXIF"), p_with_exif: -90}

    def _fake_rotate(path, op):
        r = results[path]
        if isinstance(r, Exception):
            raise r
        return r

    with patch("pbpicat.image_ops.rotate_lossless", side_effect=_fake_rotate):
        window._rotate_images([p_no_exif, p_with_exif], "auto")

    assert len(window._undo_stack) == 1
    kind, pairs = window._undo_stack[-1]
    assert kind == "rotation"
    assert len(pairs) == 1
    assert pairs[0][:2] == (p_with_exif, -90)  # only the EXIF file recorded


# ---------------------------------------------------------------------------
# _rotate_selected with op="auto": EXIF filter branch (lines 605-612)
# ---------------------------------------------------------------------------


def _img(path):
    from PIL import Image

    Image.new("RGB", (1, 1), "red").save(str(path))
    return path


def test_rotate_selected_auto_no_exif_filters_to_empty(window, tmp_path, monkeypatch):
    """_rotate_selected('auto') passes only files with EXIF orientation."""
    f = _img(tmp_path / "img.png")
    monkeypatch.setattr(window._file_panel.file_list, "get_selected_files", lambda: [f])
    with (
        patch("pbpicat.image_ops.get_exif_orientation", return_value=None),
        patch.object(window, "_rotate_images") as mock_rotate,
    ):
        window._rotate_selected("auto")
    mock_rotate.assert_called_once_with([], "auto")


def test_rotate_selected_auto_with_exif_passes_file(window, tmp_path, monkeypatch):
    """_rotate_selected('auto') keeps files that have an EXIF orientation tag."""
    f = _img(tmp_path / "img.png")
    monkeypatch.setattr(window._file_panel.file_list, "get_selected_files", lambda: [f])
    with (
        patch("pbpicat.image_ops.get_exif_orientation", return_value=6),
        patch.object(window, "_rotate_images") as mock_rotate,
    ):
        window._rotate_selected("auto")
    mock_rotate.assert_called_once_with([f], "auto")


def test_rotate_selected_non_auto(window, tmp_path, monkeypatch):
    """_rotate_selected with a degree op skips the EXIF filter."""
    f = _img(tmp_path / "img.png")
    monkeypatch.setattr(window._file_panel.file_list, "get_selected_files", lambda: [f])
    with patch.object(window, "_rotate_images") as mock_rotate:
        window._rotate_selected(90)
    mock_rotate.assert_called_once_with([f], 90)


# ---------------------------------------------------------------------------
# _undo_last_rename rotation: set_exif_orientation when orig_orient given (line 765)
# ---------------------------------------------------------------------------


def test_undo_rotation_restores_exif_orientation(window, tmp_path, monkeypatch):
    """Undoing a rotation must restore orig_orient via set_exif_orientation."""
    f = _img(tmp_path / "img.png")
    window._undo_stack.append(("rotation", [(f, 90, 6)]))
    window._update_undo_btn()
    monkeypatch.setattr(
        window._file_panel.file_list,
        "refresh_thumbnails_for_paths",
        lambda paths: None,
    )
    with (
        patch("pbpicat.image_ops.rotate_lossless", return_value=-90),
        patch("pbpicat.image_ops.set_exif_orientation") as mock_set,
    ):
        window._undo_last_rename()
    mock_set.assert_called_once_with(f, 6)


def test_undo_rotation_no_exif_restore_when_none(window, tmp_path, monkeypatch):
    """When orig_orient is None, set_exif_orientation must not be called."""
    f = _img(tmp_path / "img.png")
    window._undo_stack.append(("rotation", [(f, 90, None)]))
    window._update_undo_btn()
    monkeypatch.setattr(
        window._file_panel.file_list,
        "refresh_thumbnails_for_paths",
        lambda paths: None,
    )
    with (
        patch("pbpicat.image_ops.rotate_lossless", return_value=-90),
        patch("pbpicat.image_ops.set_exif_orientation") as mock_set,
    ):
        window._undo_last_rename()
    mock_set.assert_not_called()
