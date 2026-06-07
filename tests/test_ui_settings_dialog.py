"""Tests for src/pbpicat/ui/settings_dialog.py."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from pbpicat.config import DEFAULT_SIDECAR_EXTENSIONS, DEFAULTS
from pbpicat.ui.settings_dialog import (
    GlobalSettingsDialog,
    SettingsDialog,
    _ImageTab,
    _LanguageTab,
    _SchemaTab,
    _SidecarTab,
    _ThumbnailTab,
    _VideoTab,
)


@pytest.fixture
def config():
    return dict(DEFAULTS)


# ---------------------------------------------------------------------------
# _SchemaTab
# ---------------------------------------------------------------------------


def test_schema_tab_creation(qtbot, catalog_env, config):
    tab = _SchemaTab(config)
    qtbot.addWidget(tab)
    assert tab._count_spin.value() == config["schema_field_count"]


def test_schema_tab_rebuild_on_count_change(qtbot, catalog_env, config):
    tab = _SchemaTab(config)
    qtbot.addWidget(tab)
    tab._count_spin.setValue(3)
    assert len(tab._title_edits) == 3


def test_schema_tab_apply_to(qtbot, catalog_env, config):
    tab = _SchemaTab(config)
    qtbot.addWidget(tab)
    tab._count_spin.setValue(4)
    tab._history_spin.setValue(15)
    tab._del_list_spin.setValue(8)
    out = {}
    tab.apply_to(out)
    assert out["schema_field_count"] == 4
    assert out["history_max"] == 15
    assert out["delete_list_max_files"] == 8
    assert len(out["schema_field_titles"]) == 4


# ---------------------------------------------------------------------------
# _SidecarTab
# ---------------------------------------------------------------------------


def test_sidecar_tab_creation(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    assert tab._list.count() == len(config["sidecar_extensions"])


def test_sidecar_tab_add_ext(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    tab._ext_edit.setText(".myext")
    tab._add_ext()
    assert tab._list.count() == before + 1


def test_sidecar_tab_add_ext_auto_dot(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    tab._ext_edit.setText("noext")
    tab._add_ext()
    items = [tab._list.item(i).text() for i in range(tab._list.count())]
    assert ".noext" in items


def test_sidecar_tab_add_ext_invalid(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    with patch.object(QMessageBox, "warning", return_value=None):
        tab._ext_edit.setText("!!bad!!")
        tab._add_ext()
    assert tab._list.count() == before


def test_sidecar_tab_add_ext_duplicate_ignored(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    tab._ext_edit.setText(config["sidecar_extensions"][0])
    tab._add_ext()
    assert tab._list.count() == before


def test_sidecar_tab_del_ext(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    tab._list.setCurrentRow(0)
    tab._del_ext()
    assert tab._list.count() == before - 1


def test_sidecar_tab_del_ext_no_selection(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    tab._list.setCurrentRow(-1)
    tab._del_ext()
    assert tab._list.count() == before


def test_sidecar_tab_restore_missing_defaults(qtbot, catalog_env, config):
    config_no_sidecars = dict(config)
    config_no_sidecars["sidecar_extensions"] = []
    tab = _SidecarTab(config_no_sidecars)
    qtbot.addWidget(tab)
    with patch(
        "pbpicat.ui.settings_dialog.load_global_config",
        return_value={"default_sidecar_extensions": DEFAULT_SIDECAR_EXTENSIONS},
    ):
        tab._restore_missing_defaults()
    assert tab._list.count() > 0


def test_sidecar_tab_restore_nothing_to_add(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    with (
        patch(
            "pbpicat.ui.settings_dialog.load_global_config",
            return_value={"default_sidecar_extensions": config["sidecar_extensions"]},
        ),
        patch.object(QMessageBox, "information", return_value=None),
    ):
        tab._restore_missing_defaults()


def test_sidecar_tab_apply_to(qtbot, catalog_env, config):
    tab = _SidecarTab(config)
    qtbot.addWidget(tab)
    out = {}
    tab.apply_to(out)
    assert "sidecar_extensions" in out
    assert "sidecar_new_extension" in out
    assert "delete_empty_sidecars" in out


# ---------------------------------------------------------------------------
# _ThumbnailTab
# ---------------------------------------------------------------------------


def test_thumbnail_tab_creation(qtbot, catalog_env, config):
    tab = _ThumbnailTab(config)
    qtbot.addWidget(tab)
    assert tab._w_spin.value() == config["thumbnail_max_width"]
    assert tab._h_spin.value() == config["thumbnail_max_height"]


def test_thumbnail_tab_legacy_key(qtbot, catalog_env):
    config = {"thumbnail_size": 64}
    tab = _ThumbnailTab(config)
    qtbot.addWidget(tab)
    assert tab._w_spin.value() == 64


def test_thumbnail_tab_apply_to(qtbot, catalog_env, config):
    tab = _ThumbnailTab(config)
    qtbot.addWidget(tab)
    tab._w_spin.setValue(64)
    tab._h_spin.setValue(48)
    out = {}
    tab.apply_to(out)
    assert out == {"thumbnail_max_width": 64, "thumbnail_max_height": 48}


# ---------------------------------------------------------------------------
# _ImageTab
# ---------------------------------------------------------------------------


def test_image_tab_creation(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    assert tab._list.count() == len(config["image_extensions"])


def test_image_tab_add_ext(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    tab._ext_edit.setText(".newraw")
    tab._add_ext()
    items = [tab._list.item(i).text() for i in range(tab._list.count())]
    assert ".newraw" in items


def test_image_tab_add_ext_invalid(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    with patch.object(QMessageBox, "warning", return_value=None):
        tab._ext_edit.setText("!!bad!!")
        tab._add_ext()
    assert tab._list.count() == before


def test_image_tab_add_ext_duplicate(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    tab._ext_edit.setText(config["image_extensions"][0])
    tab._add_ext()
    assert tab._list.count() == before


def test_image_tab_del_ext(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    tab._list.setCurrentRow(0)
    before = tab._list.count()
    tab._del_ext()
    assert tab._list.count() == before - 1


def test_image_tab_del_ext_no_selection(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    tab._list.setCurrentRow(-1)
    before = tab._list.count()
    tab._del_ext()
    assert tab._list.count() == before


def test_image_tab_restore_missing_defaults(qtbot, catalog_env):
    tab = _ImageTab({"image_extensions": []})
    qtbot.addWidget(tab)
    tab._restore_missing_defaults()
    assert tab._list.count() > 0


def test_image_tab_restore_nothing_to_add(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    with patch.object(QMessageBox, "information", return_value=None):
        tab._restore_missing_defaults()


def test_image_tab_apply_to_confirm_deletions(qtbot, catalog_env, config):
    tab = _ImageTab(config)
    qtbot.addWidget(tab)
    tab._confirm_deletions_cb.setChecked(False)
    out = {}
    tab.apply_to(out)
    assert out["confirm_deletions"] is False


# ---------------------------------------------------------------------------
# _VideoTab
# ---------------------------------------------------------------------------


def test_video_tab_creation(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    assert tab._list.count() == len(config["video_extensions"])


def test_video_tab_add_ext(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    tab._ext_edit.setText(".myv")
    tab._add_ext()
    items = [tab._list.item(i).text() for i in range(tab._list.count())]
    assert ".myv" in items


def test_video_tab_add_ext_invalid(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    with patch.object(QMessageBox, "warning", return_value=None):
        tab._ext_edit.setText("@@bad@@")
        tab._add_ext()
    assert tab._list.count() == before


def test_video_tab_add_ext_duplicate(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    before = tab._list.count()
    tab._ext_edit.setText(config["video_extensions"][0])
    tab._add_ext()
    assert tab._list.count() == before


def test_video_tab_del_ext(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    tab._list.setCurrentRow(0)
    before = tab._list.count()
    tab._del_ext()
    assert tab._list.count() == before - 1


def test_video_tab_del_ext_no_selection(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    tab._list.setCurrentRow(-1)
    before = tab._list.count()
    tab._del_ext()
    assert tab._list.count() == before


def test_video_tab_restore_defaults(qtbot, catalog_env):
    tab = _VideoTab({"video_extensions": []})
    qtbot.addWidget(tab)
    tab._restore_missing_defaults()
    assert tab._list.count() > 0


def test_video_tab_restore_nothing_to_add(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    with patch.object(QMessageBox, "information", return_value=None):
        tab._restore_missing_defaults()


def test_video_tab_apply_to(qtbot, catalog_env, config):
    tab = _VideoTab(config)
    qtbot.addWidget(tab)
    tab._marker_edit.setText("VID")
    out = {}
    tab.apply_to(out)
    assert out["video_marker"] == "VID"
    assert "video_extensions" in out


# ---------------------------------------------------------------------------
# _LanguageTab
# ---------------------------------------------------------------------------


def test_language_tab_creation(qtbot, catalog_env, config):
    tab = _LanguageTab(config)
    qtbot.addWidget(tab)
    assert tab._lang_combo.count() > 0


def test_language_tab_apply_to(qtbot, catalog_env, config):
    tab = _LanguageTab(config)
    qtbot.addWidget(tab)
    out = {}
    tab.apply_to(out)
    assert "language" in out


# ---------------------------------------------------------------------------
# SettingsDialog
# ---------------------------------------------------------------------------


def test_settings_dialog_creation(qtbot, catalog_env, config):
    dlg = SettingsDialog(config)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() != ""


def test_settings_dialog_accept(qtbot, catalog_env, config):
    dlg = SettingsDialog(config)
    qtbot.addWidget(dlg)
    with patch("pbpicat.ui.settings_dialog.save_config"):
        dlg._accept()
    result = dlg.updated_config()
    assert "schema_field_count" in result


# ---------------------------------------------------------------------------
# GlobalSettingsDialog
# ---------------------------------------------------------------------------


def test_global_settings_dialog_creation(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    assert dlg._list.count() > 0


def test_global_settings_add_ext(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    before = dlg._list.count()
    dlg._ext_edit.setText(".mysc")
    dlg._add_ext()
    assert dlg._list.count() == before + 1


def test_global_settings_add_ext_invalid(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    before = dlg._list.count()
    with patch.object(QMessageBox, "warning", return_value=None):
        dlg._ext_edit.setText("!!bad!!")
        dlg._add_ext()
    assert dlg._list.count() == before


def test_global_settings_add_ext_duplicate(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    before = dlg._list.count()
    existing = dlg._list.item(0).text()
    dlg._ext_edit.setText(existing)
    dlg._add_ext()
    assert dlg._list.count() == before


def test_global_settings_del_ext(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    before = dlg._list.count()
    dlg._list.setCurrentRow(0)
    dlg._del_ext()
    assert dlg._list.count() == before - 1


def test_global_settings_del_ext_no_selection(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    before = dlg._list.count()
    dlg._list.setCurrentRow(-1)
    dlg._del_ext()
    assert dlg._list.count() == before


def test_global_settings_restore_defaults(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    dlg._list.clear()
    dlg._restore_defaults()
    assert dlg._list.count() == len(DEFAULT_SIDECAR_EXTENSIONS)


def test_global_settings_accept(qtbot, catalog_env):
    dlg = GlobalSettingsDialog()
    qtbot.addWidget(dlg)
    with patch("pbpicat.ui.settings_dialog.save_global_config"):
        dlg._accept()
    cfg = dlg.updated_global_config()
    assert "default_sidecar_extensions" in cfg
    assert "language" in cfg
