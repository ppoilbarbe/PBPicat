"""Tests for src/pbpicat/ui/dir_tree.py."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt

import pbpicat.ui.dir_tree as _dtmod
from pbpicat.ui.dir_tree import DirTree

# ---------------------------------------------------------------------------
# Module-level patches applied to every test in this file
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_qmenu(monkeypatch):
    """Patch QMenu in the dir_tree module so menu.exec() never blocks.

    Returns the MagicMock instance so individual tests can inspect/configure it.
    By default exec() returns None (cancel).
    """
    mock = MagicMock()
    mock.exec.return_value = None
    monkeypatch.setattr(_dtmod, "QMenu", lambda parent=None: mock)
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tree_with_model(qtbot):
    tree = DirTree()
    qtbot.addWidget(tree)
    mock_file_list = MagicMock()
    tree.set_file_list(mock_file_list)
    return tree, mock_file_list


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_dir_tree_creation(qtbot):
    tree = DirTree()
    qtbot.addWidget(tree)
    assert tree._file_list is None
    assert tree._target_path is None


def test_dir_tree_set_file_list(tree_with_model):
    tree, mock_fl = tree_with_model
    assert tree._model is not None
    assert tree._file_list is mock_fl


# ---------------------------------------------------------------------------
# current_path / select_path
# ---------------------------------------------------------------------------


def test_current_path_returns_string(tree_with_model):
    tree, _ = tree_with_model
    path = tree.current_path()
    assert isinstance(path, str)


def test_select_path_nonexistent_no_op(tree_with_model):
    tree, _ = tree_with_model
    tree.select_path("/no/such/path/xyz/abc")
    assert tree._target_path is None


def test_select_path_valid(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    tree.select_path(str(tmp_path))
    assert tree._scroll_path == str(tmp_path)


# ---------------------------------------------------------------------------
# _on_directory_loaded
# ---------------------------------------------------------------------------


def test_on_directory_loaded_related_target(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    sub = str(tmp_path / "sub")
    tree._target_path = sub
    tree._on_directory_loaded(str(tmp_path))


def test_on_directory_loaded_unrelated(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    other = str(tmp_path / "other_branch")
    tree._target_path = str(tmp_path / "a_sub")
    tree._on_directory_loaded(other)
    assert tree._target_path == str(tmp_path / "a_sub")


def test_on_directory_loaded_scroll_path(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    tree._scroll_path = str(tmp_path / "scroll_target")
    tree._on_directory_loaded(str(tmp_path))


def test_on_directory_loaded_no_target(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    tree._target_path = None
    tree._scroll_path = None
    tree._on_directory_loaded(str(tmp_path))


# ---------------------------------------------------------------------------
# _on_current_changed
# ---------------------------------------------------------------------------


def test_on_current_changed_clears_target(tree_with_model):
    tree, mock_fl = tree_with_model
    tree._target_path = "/some/path"
    tree._scroll_path = "/some/path"
    idx = tree.currentIndex()
    if idx.isValid():
        tree._on_current_changed(idx, idx)
        assert tree._target_path is None


def test_on_current_changed_clears_scroll_if_different(tree_with_model):
    tree, _ = tree_with_model
    tree._scroll_path = "/different/path"
    idx = tree.currentIndex()
    if idx.isValid():
        tree._on_current_changed(idx, idx)


# ---------------------------------------------------------------------------
# showEvent and _do_scroll
# ---------------------------------------------------------------------------


def test_show_event_with_scroll_path(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    tree._scroll_path = str(tmp_path)
    tree.show()
    tree.hide()


def test_show_event_no_scroll_path(tree_with_model):
    tree, _ = tree_with_model
    tree._scroll_path = None
    tree.show()
    tree.hide()


def test_do_scroll_hidden(tree_with_model, tmp_path):
    tree, _ = tree_with_model
    tree._scroll_path = str(tmp_path)
    tree.hide()
    tree._do_scroll()


# ---------------------------------------------------------------------------
# keyPressEvent
# ---------------------------------------------------------------------------


def test_key_press_right_no_file_list(tree_with_model, qtbot):
    tree, mock_fl = tree_with_model
    qtbot.keyClick(tree, Qt.Key_Right)


def test_key_press_other_key(tree_with_model):
    tree, _ = tree_with_model
    from PySide6.QtGui import QKeyEvent

    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Down, Qt.NoModifier)
    tree.keyPressEvent(event)


def test_key_press_right_with_file_list(tree_with_model, qtbot):
    tree, mock_fl = tree_with_model
    qtbot.keyClick(tree, Qt.Key_Right)


# ---------------------------------------------------------------------------
# Context menu
# ---------------------------------------------------------------------------


def test_show_context_menu_invalid_pos(tree_with_model):
    """Invalid index → early return before QMenu is created."""
    from PySide6.QtCore import QPoint

    tree, _ = tree_with_model
    tree._show_context_menu(QPoint(-1, -1))


def test_show_context_menu_valid_pos_cancel(tree_with_model, qtbot, mock_qmenu):
    """Valid index + cancel (exec returns None) → no URL opened."""
    tree, _ = tree_with_model
    tree.show()
    idx = tree.currentIndex()
    if idx.isValid():
        rect = tree.visualRect(idx)
        tree._show_context_menu(rect.center())
        # exec returns None (the autouse default) → no openUrl call
    tree.hide()


def test_show_context_menu_open_url(tree_with_model, qtbot, mock_qmenu, monkeypatch):
    """Valid index + exec returns the open action → QDesktopServices.openUrl called."""
    tree, _ = tree_with_model
    tree.show()

    open_calls = []
    monkeypatch.setattr(
        _dtmod,
        "QDesktopServices",
        type("_FakeQDS", (), {"openUrl": staticmethod(lambda url: open_calls.append(url))})(),
    )

    idx = tree.currentIndex()
    if not idx.isValid():
        tree.hide()
        return

    # Make exec() return whatever addAction() returned, so "if action is open_action" is True
    open_action_mock = MagicMock()
    mock_qmenu.addAction.return_value = open_action_mock
    mock_qmenu.exec.return_value = open_action_mock

    rect = tree.visualRect(idx)
    tree._show_context_menu(rect.center())
    assert len(open_calls) == 1
    tree.hide()


def test_try_select_early_return(tree_with_model):
    """_try_select returns early when _target_path is None."""
    tree, _ = tree_with_model
    tree._target_path = None
    tree._try_select()
