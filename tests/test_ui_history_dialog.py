"""Tests for src/pbpicat/ui/history_dialog.py."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from pbpicat.config import DEFAULTS
from pbpicat.ui.history_dialog import HistoryDialog, _FieldHistoryWidget


@pytest.fixture
def config(catalog_env):
    return dict(DEFAULTS)


# ---------------------------------------------------------------------------
# _FieldHistoryWidget
# ---------------------------------------------------------------------------


def test_field_history_widget_creation(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Category", ["Alpha", "Beta", "Gamma"])
    qtbot.addWidget(w)
    assert w._list.count() == 3


def test_field_history_widget_empty(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Category", [])
    qtbot.addWidget(w)
    assert w._list.count() == 0


def test_field_history_widget_get_items(qtbot, catalog_env):
    items = ["A", "B", "C"]
    w = _FieldHistoryWidget("field_0", "Cat", items)
    qtbot.addWidget(w)
    assert w.get_items() == items


def test_field_history_widget_key_property(qtbot, catalog_env):
    w = _FieldHistoryWidget("my_key", "Title", [])
    qtbot.addWidget(w)
    assert w.key == "my_key"


def test_field_history_widget_move_up(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B", "C"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(1)
    w._move_up()
    assert w._list.item(0).text() == "B"
    assert w._list.item(1).text() == "A"


def test_field_history_widget_move_up_at_top(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(0)
    w._move_up()
    assert w._list.item(0).text() == "A"


def test_field_history_widget_move_down(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B", "C"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(1)
    w._move_down()
    assert w._list.item(2).text() == "B"


def test_field_history_widget_move_down_at_bottom(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(1)
    w._move_down()
    assert w._list.item(1).text() == "B"


def test_field_history_widget_move_down_no_selection(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(-1)
    w._move_down()  # no crash


def test_field_history_widget_delete_selected(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B", "C"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(1)
    w._delete_selected()
    assert w._list.count() == 2
    assert w.get_items() == ["A", "C"]


def test_field_history_widget_delete_no_selection(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(-1)
    w._delete_selected()
    assert w._list.count() == 1


def test_field_history_widget_clear_all(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B"])
    qtbot.addWidget(w)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        w._clear_all()
    assert w._list.count() == 0


def test_field_history_widget_clear_all_cancelled(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B"])
    qtbot.addWidget(w)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        w._clear_all()
    assert w._list.count() == 2


def test_field_history_widget_clear_all_empty(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", [])
    qtbot.addWidget(w)
    w._clear_all()  # should not show dialog when empty
    assert w._list.count() == 0


def test_field_history_widget_update_buttons(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B", "C"])
    qtbot.addWidget(w)
    w._list.setCurrentRow(0)
    w._update_buttons(0)
    assert not w._up_btn.isEnabled()
    assert w._down_btn.isEnabled()
    assert w._del_btn.isEnabled()


def test_field_history_widget_update_buttons_middle(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A", "B", "C"])
    qtbot.addWidget(w)
    w._update_buttons(1)
    assert w._up_btn.isEnabled()
    assert w._down_btn.isEnabled()


def test_field_history_widget_update_buttons_no_selection(qtbot, catalog_env):
    w = _FieldHistoryWidget("field_0", "Cat", ["A"])
    qtbot.addWidget(w)
    w._update_buttons(-1)
    assert not w._del_btn.isEnabled()


# ---------------------------------------------------------------------------
# HistoryDialog
# ---------------------------------------------------------------------------


def test_history_dialog_creation(qtbot, config, catalog_env):
    dlg = HistoryDialog(config)
    qtbot.addWidget(dlg)
    assert len(dlg._field_widgets) == config["schema_field_count"] + 1  # +1 for sidecar_filter


def test_history_dialog_accept_saves(qtbot, config, catalog_env):
    dlg = HistoryDialog(config)
    qtbot.addWidget(dlg)
    dlg._field_widgets[0]._list.addItem("TestValue")
    with patch("pbpicat.ui.history_dialog.save_all_history") as mock_save:
        dlg._accept()
        mock_save.assert_called_once()


def test_history_dialog_with_titles(qtbot, catalog_env):
    config = {
        "schema_field_count": 3,
        "schema_field_titles": ["Cat1", "Cat2", "Cat3"],
    }
    dlg = HistoryDialog(config)
    qtbot.addWidget(dlg)
    assert len(dlg._field_widgets) == 4  # 3 + sidecar_filter
