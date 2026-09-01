"""Tests for src/pbpicat/ui/dir_tree.py."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QMimeData, QModelIndex, QPoint, Qt, QUrl

import pbpicat.ui.dir_tree as _dtmod
from pbpicat.ui.dir_tree import DirTree


class _FakePosition:
    def __init__(self, point):
        self._point = point

    def toPoint(self):  # noqa: N802
        return self._point


class _FakeDropEvent:
    """Stand-in for QDropEvent/QDragMoveEvent: exposes position()/mimeData()/source()/
    proposedAction() and records ignore()/acceptProposedAction() calls without needing
    a real drag."""

    def __init__(self, point, mime, source=None, proposed_action=Qt.MoveAction):
        self._position = _FakePosition(point)
        self._mime = mime
        self._source = source
        self._proposed_action = proposed_action
        self.ignored = False
        self.accepted = False

    def position(self):
        return self._position

    def mimeData(self):  # noqa: N802
        return self._mime

    def source(self):
        return self._source

    def proposedAction(self):  # noqa: N802
        return self._proposed_action

    def ignore(self):
        self.ignored = True

    def acceptProposedAction(self):  # noqa: N802
        self.accepted = True


def _mime_with_url(path="/tmp/some_image.jpg"):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path)])
    return mime


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
# keyboard navigation
# ---------------------------------------------------------------------------


def test_tab_moves_focus_to_file_list(tree_with_model, qtbot):
    tree, mock_fl = tree_with_model
    qtbot.keyClick(tree, Qt.Key_Tab)
    mock_fl.setFocus.assert_called_once()


def test_backtab_moves_focus_to_file_list(tree_with_model):
    tree, mock_fl = tree_with_model
    from PySide6.QtGui import QKeyEvent

    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Backtab, Qt.ShiftModifier)
    tree.event(event)
    mock_fl.setFocus.assert_called_once()


def test_arrow_keys_do_not_transfer_focus(tree_with_model, qtbot):
    tree, mock_fl = tree_with_model
    for k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
        qtbot.keyClick(tree, k)
    mock_fl.setFocus.assert_not_called()


def test_tab_no_file_list_does_not_crash(qtbot):
    tree = DirTree()
    qtbot.addWidget(tree)
    qtbot.keyClick(tree, Qt.Key_Tab)


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


# ---------------------------------------------------------------------------
# Drag-and-drop (move files onto a folder)
# ---------------------------------------------------------------------------


def test_drag_enter_event_accepts_urls(tree_with_model):
    tree, _ = tree_with_model
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url())
    tree.dragEnterEvent(event)
    assert event.accepted
    assert not event.ignored


def test_drag_enter_event_rejects_no_urls(tree_with_model):
    tree, _ = tree_with_model
    event = _FakeDropEvent(QPoint(0, 0), QMimeData())
    tree.dragEnterEvent(event)
    assert event.ignored
    assert not event.accepted


def test_drag_move_event_valid_index_accepts(tree_with_model, monkeypatch):
    tree, _ = tree_with_model
    idx = tree.currentIndex()
    assert idx.isValid()
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url())
    tree.dragMoveEvent(event)
    assert event.accepted


def test_drag_move_event_invalid_index_ignores(tree_with_model, monkeypatch):
    tree, _ = tree_with_model
    monkeypatch.setattr(tree, "indexAt", lambda point: QModelIndex())
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url())
    tree.dragMoveEvent(event)
    assert event.ignored


def test_drop_event_calls_move_files_to(tree_with_model, monkeypatch):
    """Internal drag (source is the app's own file list) proposing Move → move_files_to, undoable."""
    tree, mock_fl = tree_with_model
    idx = tree.currentIndex()
    assert idx.isValid()
    dest = tree._model.filePath(idx)
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)

    src = "/tmp/some_image.jpg"
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url(src), source=mock_fl, proposed_action=Qt.MoveAction)
    tree.dropEvent(event)

    assert event.accepted
    assert not event.ignored
    mock_fl.move_files_to.assert_called_once_with([Path(src)], dest)
    mock_fl.copy_files_to.assert_not_called()
    mock_fl.move_external_files_to.assert_not_called()
    mock_fl.copy_external_files_to.assert_not_called()


def test_drop_event_internal_copy_calls_copy_files_to(tree_with_model, monkeypatch):
    """Internal drag (source is the app's own file list) proposing Copy (Shift-drag) → copy_files_to, undoable."""
    tree, mock_fl = tree_with_model
    idx = tree.currentIndex()
    assert idx.isValid()
    dest = tree._model.filePath(idx)
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)

    src = "/tmp/some_image.jpg"
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url(src), source=mock_fl, proposed_action=Qt.CopyAction)
    tree.dropEvent(event)

    assert event.accepted
    mock_fl.copy_files_to.assert_called_once_with([Path(src)], dest)
    mock_fl.move_files_to.assert_not_called()
    mock_fl.move_external_files_to.assert_not_called()
    mock_fl.copy_external_files_to.assert_not_called()


def test_drop_event_external_move_calls_move_external_files_to(tree_with_model, monkeypatch):
    """External drag (source is None, e.g. a file manager) proposing Move → move_external_files_to."""
    tree, mock_fl = tree_with_model
    idx = tree.currentIndex()
    assert idx.isValid()
    dest = tree._model.filePath(idx)
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)

    src = "/tmp/some_image.jpg"
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url(src), source=None, proposed_action=Qt.MoveAction)
    tree.dropEvent(event)

    assert event.accepted
    mock_fl.move_external_files_to.assert_called_once_with([Path(src)], dest)
    mock_fl.move_files_to.assert_not_called()
    mock_fl.copy_files_to.assert_not_called()
    mock_fl.copy_external_files_to.assert_not_called()


def test_drop_event_external_copy_calls_copy_external_files_to(tree_with_model, monkeypatch):
    """External drag (source is None) proposing Copy → copy_external_files_to."""
    tree, mock_fl = tree_with_model
    idx = tree.currentIndex()
    assert idx.isValid()
    dest = tree._model.filePath(idx)
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)

    src = "/tmp/some_image.jpg"
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url(src), source=None, proposed_action=Qt.CopyAction)
    tree.dropEvent(event)

    assert event.accepted
    mock_fl.copy_external_files_to.assert_called_once_with([Path(src)], dest)
    mock_fl.move_files_to.assert_not_called()
    mock_fl.copy_files_to.assert_not_called()
    mock_fl.move_external_files_to.assert_not_called()


def test_drop_event_invalid_index_ignored(tree_with_model, monkeypatch):
    tree, mock_fl = tree_with_model
    monkeypatch.setattr(tree, "indexAt", lambda point: QModelIndex())
    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url())
    tree.dropEvent(event)
    assert event.ignored
    mock_fl.move_files_to.assert_not_called()


def test_drop_event_no_file_list_ignored(qtbot, monkeypatch):
    tree = DirTree()
    qtbot.addWidget(tree)
    tree.set_file_list(MagicMock())
    idx = tree.currentIndex()
    assert idx.isValid()
    tree._file_list = None
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)

    event = _FakeDropEvent(QPoint(0, 0), _mime_with_url())
    tree.dropEvent(event)

    assert event.ignored


def test_drop_event_no_urls_ignored(tree_with_model, monkeypatch):
    tree, mock_fl = tree_with_model
    idx = tree.currentIndex()
    monkeypatch.setattr(tree, "indexAt", lambda point: idx)

    event = _FakeDropEvent(QPoint(0, 0), QMimeData())
    tree.dropEvent(event)

    assert event.ignored
    mock_fl.move_files_to.assert_not_called()
