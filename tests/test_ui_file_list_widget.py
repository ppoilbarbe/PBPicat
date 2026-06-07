"""Tests for src/pbpicat/ui/file_list_widget.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as _PilImage
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMessageBox

import pbpicat.ui.file_list_widget as _flmod
from pbpicat.config import DEFAULTS
from pbpicat.ui.file_list_widget import FileListWidget, _natural_sort_key, _SchemaProposalDialog, _ThumbnailWorker


def _img(path):
    """Create a minimal valid 1x1 RGB PNG at path."""
    _PilImage.new("RGB", (1, 1), "red").save(str(path))
    return path


# ---------------------------------------------------------------------------
# _natural_sort_key
# ---------------------------------------------------------------------------


def test_natural_sort_key_pads_numbers():
    p1 = Path("abc_2.jpg")
    p2 = Path("abc_10.jpg")
    assert _natural_sort_key(p1) < _natural_sort_key(p2)


def test_natural_sort_key_normalizes_accents():
    p = Path("Été.jpg")
    key = _natural_sort_key(p)
    assert "é" not in key.lower()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_thumbnail_thread(monkeypatch):
    """Prevent background thumbnail thread in all FileListWidget tests."""
    monkeypatch.setattr(FileListWidget, "_start_worker", lambda self: None)


@pytest.fixture(autouse=True)
def mock_qmenu(monkeypatch):
    """Patch QMenu at module level so menu.exec() never blocks.

    Default: exec() returns None (cancel). Tests can configure the returned mock.
    """
    mock = MagicMock()
    mock.exec.return_value = None
    monkeypatch.setattr(_flmod, "QMenu", lambda parent=None: mock)
    return mock


@pytest.fixture
def base_config(catalog_env):
    c = dict(DEFAULTS)
    c["confirm_deletions"] = False
    c["delete_empty_sidecars"] = False
    return c


@pytest.fixture
def widget(qtbot, base_config):
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    return w


@pytest.fixture
def populated_widget(qtbot, base_config, tmp_path):
    _img(tmp_path / "img_001.png")
    _img(tmp_path / "img_002.png")
    (tmp_path / "img_001.xmp").write_text("<meta/>")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    return w, tmp_path


# ---------------------------------------------------------------------------
# _ThumbnailWorker
# ---------------------------------------------------------------------------


def test_thumbnail_worker_cancel(tmp_path):
    files = [tmp_path / "a.png", tmp_path / "b.png"]
    for f in files:
        _img(f)
    worker = _ThumbnailWorker(files, 64, 64, {".jpg"})
    worker.cancel()
    assert worker._cancelled


def test_thumbnail_worker_run_skips_non_image(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("text")
    worker = _ThumbnailWorker([f], 64, 64, {".jpg"})
    emitted = []
    worker.thumbnail_ready.connect(lambda row, img: emitted.append(row))
    worker.run()
    assert emitted == []


def test_thumbnail_worker_run_cancelled_immediately(tmp_path):
    f = tmp_path / "a.png"
    _img(f)
    worker = _ThumbnailWorker([f], 64, 64, {".jpg"})
    worker._cancelled = True
    emitted = []
    worker.thumbnail_ready.connect(lambda row, img: emitted.append(row))
    worker.run()
    assert emitted == []


# ---------------------------------------------------------------------------
# _SchemaProposalDialog
# ---------------------------------------------------------------------------


def test_schema_proposal_dialog_with_values(qtbot, catalog_env):
    dlg = _SchemaProposalDialog(["Cat", "Sub"], ["Nature", "Birds"])
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() != ""


def test_schema_proposal_dialog_with_empty(qtbot, catalog_env):
    dlg = _SchemaProposalDialog(["Cat", "Sub"], ["", ""])
    qtbot.addWidget(dlg)


# ---------------------------------------------------------------------------
# FileListWidget construction
# ---------------------------------------------------------------------------


def test_widget_creation(widget):
    assert widget.rowCount() == 0
    assert widget.columnCount() == 3


def test_widget_get_selected_files_empty(widget):
    assert widget.get_selected_files() == []


def test_widget_get_all_files_empty(widget):
    assert widget.get_all_files() == []


# ---------------------------------------------------------------------------
# load_directory and _scan_directory
# ---------------------------------------------------------------------------


def test_load_directory_empty(qtbot, base_config, tmp_path):
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert w.rowCount() == 0


def test_load_directory_with_images(populated_widget):
    w, d = populated_widget
    assert w.rowCount() == 2


def test_load_directory_with_orphan_sidecar(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    (tmp_path / "orphan.xmp").write_text("<o/>")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert len(w.get_orphan_sidecars()) == 1


def test_load_directory_deletes_empty_sidecar(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["delete_empty_sidecars"] = True
    config["confirm_deletions"] = False
    _img(tmp_path / "img.png")
    empty_sc = tmp_path / "img.xmp"
    empty_sc.write_bytes(b"")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert not empty_sc.exists()


def test_load_directory_oserror(qtbot, base_config, tmp_path):
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w._current_dir = tmp_path / "nonexistent"
    w._scan_directory()
    assert w._file_data == []


def test_sort_by_date(qtbot, base_config, tmp_path):
    for name in ["a.png", "b.png"]:
        _img(tmp_path / name)
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_sort_by_date(True)
    assert w.rowCount() == 2


def test_sort_reverse(qtbot, base_config, tmp_path):
    for name in ["a.png", "b.png"]:
        _img(tmp_path / name)
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_sort_reverse(True)
    names = [w._display_data[i][0].name for i in range(w.rowCount())]
    assert names[0] == "b.png"


# ---------------------------------------------------------------------------
# Sidecar filter
# ---------------------------------------------------------------------------


def test_sidecar_filter_matches(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    (tmp_path / "img.xmp").write_text("keyword: nature")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_sidecar_filter("nature")
    assert w.rowCount() == 1


def test_sidecar_filter_no_match(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    (tmp_path / "img.xmp").write_text("keyword: nature")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_sidecar_filter("zzz_nomatch")
    assert w.rowCount() == 0


def test_sidecar_filter_invalid_regex(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_sidecar_filter("[invalid")
    assert w.rowCount() == 1


def test_sidecar_filter_no_sidecar_file(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_sidecar_filter("nature")
    assert w.rowCount() == 0


def test_sidecar_filter_oserror(qtbot, base_config, tmp_path, monkeypatch):
    _img(tmp_path / "img.png")
    (tmp_path / "img.xmp").write_text("data")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    import pathlib

    orig = pathlib.Path.read_text

    def mock_read(self, *a, **kw):
        if self.suffix == ".xmp":
            raise OSError("denied")
        return orig(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", mock_read)
    w.set_sidecar_filter("data")
    assert w.rowCount() == 0


# ---------------------------------------------------------------------------
# get_selected_files / next_row_after_files
# ---------------------------------------------------------------------------


def test_get_selected_files(populated_widget):
    w, d = populated_widget
    w.selectRow(0)
    files = w.get_selected_files()
    assert len(files) == 1


def test_get_all_files(populated_widget):
    w, d = populated_widget
    assert len(w.get_all_files()) == 2


def test_next_row_after_files_empty(widget):
    assert widget.next_row_after_files([]) == 0


def test_next_row_after_files_last(populated_widget):
    w, d = populated_widget
    paths = [p for p, _ in w._display_data]
    row = w.next_row_after_files(paths)
    assert row == 0


def test_next_row_after_files_first(populated_widget):
    w, d = populated_widget
    first = w._display_data[0][0]
    row = w.next_row_after_files([first])
    # Removing first file: nothing before it is kept → new list starts at 0
    assert row == 0


# ---------------------------------------------------------------------------
# refresh_and_select / reconfigure
# ---------------------------------------------------------------------------


def test_refresh_and_select(populated_widget):
    w, d = populated_widget
    w.refresh_and_select(0)
    assert w.rowCount() == 2


def test_refresh_and_select_beyond_end(populated_widget):
    w, d = populated_widget
    w.refresh_and_select(999)
    assert w.selectedIndexes()


def test_reconfigure(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    _img(tmp_path / "img.png")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    new_config = dict(config)
    new_config["thumbnail_max_width"] = 64
    w.reconfigure(new_config)
    assert w._thumb_w == 64


# ---------------------------------------------------------------------------
# _delete_file (no confirmation)
# ---------------------------------------------------------------------------


def test_delete_file_removes_file(qtbot, base_config, tmp_path):
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert w.rowCount() == 1
    w.selectRow(0)
    w._delete_file(f, [])
    assert not f.exists()


def test_delete_file_removes_sidecar(qtbot, base_config, tmp_path):
    f = tmp_path / "img.png"
    sc = tmp_path / "img.xmp"
    _img(f)
    sc.write_text("<meta/>")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._delete_file(f, [sc])
    assert not sc.exists()


def test_delete_file_with_oserror(qtbot, base_config, tmp_path, monkeypatch):
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.selectRow(0)

    def mock_unlink(self, missing_ok=False):
        raise OSError("device busy")

    monkeypatch.setattr(Path, "unlink", mock_unlink)
    with patch.object(QMessageBox, "warning", return_value=None):
        w._delete_file(f, [])


def test_delete_file_count_exceeds_max(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = True
    config["delete_list_max_files"] = 1
    config["delete_empty_sidecars"] = False
    files = []
    for i in range(3):
        f = tmp_path / f"img_{i:03d}.jpg"
        _img(f)
        files.append(f)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
        w._delete_file(files[0], [])


def test_delete_file_with_confirmation(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = True
    config["delete_empty_sidecars"] = False
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes):
        w._delete_file(f, [])
    assert not f.exists()


# ---------------------------------------------------------------------------
# _remove_empty_parents
# ---------------------------------------------------------------------------


def test_remove_empty_parents_removes_empty(qtbot, base_config, tmp_path):
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w._remove_empty_parents(sub)
    assert not (tmp_path / "a").exists()


def test_remove_empty_parents_stops_at_non_empty(qtbot, base_config, tmp_path):
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    (tmp_path / "a" / "keep.txt").write_text("x")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w._remove_empty_parents(sub)
    assert (tmp_path / "a").exists()


# ---------------------------------------------------------------------------
# _is_sidecar_name
# ---------------------------------------------------------------------------


def test_is_sidecar_name_true(widget):
    assert widget._is_sidecar_name("img.xmp")


def test_is_sidecar_name_false(widget):
    assert not widget._is_sidecar_name("img.png")


def test_is_sidecar_name_just_ext(widget):
    assert not widget._is_sidecar_name(".xmp")


# ---------------------------------------------------------------------------
# _infer_schema
# ---------------------------------------------------------------------------


def test_infer_schema_no_history(widget):
    result = widget._infer_schema(Path("abc_def_001.jpg"))
    assert result is None


def test_infer_schema_with_history(qtbot, catalog_env):
    from pbpicat.config import save_history

    save_history("field_0", ["Nature"])
    save_history("field_1", ["Birds"])
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    result = w._infer_schema(Path("Nature_Birds_001.jpg"))
    assert result is not None
    assert result[0] == "Nature"
    assert result[1] == "Birds"


def test_infer_schema_numeric_field(qtbot, catalog_env):
    from pbpicat.config import save_history

    save_history("field_0", ["Nature", "###"])
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    result = w._infer_schema(Path("Nature_001.jpg"))
    assert result is not None


# ---------------------------------------------------------------------------
# _compute_preview_name
# ---------------------------------------------------------------------------


def test_compute_preview_name_no_getter(widget):
    assert widget._compute_preview_name(Path("img.png")) == ""


def test_compute_preview_name_with_getter(qtbot, catalog_env):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.set_schema_getter(lambda: ["Nature", "Birds", "", "", "", ""])
    result = w._compute_preview_name(Path("img.png"))
    assert "Nature" in result


def test_compute_preview_name_exception_returns_empty(qtbot, catalog_env):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.set_schema_getter(lambda: (_ for _ in ()).throw(RuntimeError("bad")))
    assert w._compute_preview_name(Path("img.png")) == ""


# ---------------------------------------------------------------------------
# keyPressEvent
# ---------------------------------------------------------------------------


def test_keypressevent_return_opens_single(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.selectRow(0)
    with patch.object(w, "_on_double_click") as mock_dbl:
        qtbot.keyClick(w, Qt.Key_Return)
        mock_dbl.assert_called_once()


def test_keypressevent_left_focuses_dir_tree(qtbot, base_config, tmp_path):
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    mock_tree = MagicMock()
    w.set_dir_tree(mock_tree)
    qtbot.keyClick(w, Qt.Key_Left)
    mock_tree.setFocus.assert_called_once()


def test_keypressevent_return_no_selection(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.clearSelection()
    with patch.object(w, "_on_double_click") as mock_dbl:
        qtbot.keyClick(w, Qt.Key_Return)
        mock_dbl.assert_not_called()


# ---------------------------------------------------------------------------
# focusInEvent
# ---------------------------------------------------------------------------


def test_focus_in_event_selects_first_row(populated_widget, qtbot):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent

    w, d = populated_widget
    w.clearSelection()
    # Trigger focus by key or direct call with real event
    event = QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.OtherFocusReason)
    w.focusInEvent(event)
    assert len(w.selectedIndexes()) > 0


def test_focus_in_event_empty_list(widget):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent

    event = QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.OtherFocusReason)
    widget.focusInEvent(event)  # no crash when empty


# ---------------------------------------------------------------------------
# open/delete/template slots
# ---------------------------------------------------------------------------


def test_open_selected(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch("pbpicat.ui.file_list_widget.open_default") as mock_open:
        w.open_selected()
        mock_open.assert_called_once()


def test_open_with_selected(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch("pbpicat.ui.file_list_widget.open_with") as mock_open:
        w.open_with_selected()
        mock_open.assert_called_once()


def test_template_selected_single(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch.object(w, "_propose_schema") as mock_p:
        w.template_selected()
        mock_p.assert_called_once()


def test_template_selected_multi(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectAll()
    with patch.object(w, "_propose_schema") as mock_p:
        w.template_selected()
        mock_p.assert_not_called()


def test_delete_selected(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch.object(w, "_delete_file") as mock_del:
        w.delete_selected()
        mock_del.assert_called_once()


def test_delete_selected_empty(widget, monkeypatch):
    with patch.object(widget, "_delete_file") as mock_del:
        widget.delete_selected()
        mock_del.assert_not_called()


# ---------------------------------------------------------------------------
# _viewer_row helper
# ---------------------------------------------------------------------------


def test_viewer_row_no_selection(widget):
    assert widget._viewer_row() is None


def test_viewer_row_multiple_selection(populated_widget):
    w, d = populated_widget
    w.selectAll()
    assert w._viewer_row() is None


def test_viewer_row_single_selection(populated_widget):
    w, d = populated_widget
    w.selectRow(0)
    row = w._viewer_row()
    assert row == 0


# ---------------------------------------------------------------------------
# Viewer helpers (_open_from_viewer, _delete_from_viewer, etc.)
# ---------------------------------------------------------------------------


def test_open_from_viewer_no_selection(widget, monkeypatch):
    with patch("pbpicat.ui.file_list_widget.open_default") as mock:
        widget._open_from_viewer()
        mock.assert_not_called()


def test_open_from_viewer_with_selection(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch("pbpicat.ui.file_list_widget.open_default") as mock:
        w._open_from_viewer()
        mock.assert_called_once()


def test_open_with_from_viewer_no_selection(widget, monkeypatch):
    with patch("pbpicat.ui.file_list_widget.open_with") as mock:
        widget._open_with_from_viewer()
        mock.assert_not_called()


def test_template_from_viewer_no_selection(widget, monkeypatch):
    with patch.object(widget, "_propose_schema") as mock:
        widget._template_from_viewer()
        mock.assert_not_called()


def test_template_from_viewer_with_selection(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch.object(w, "_propose_schema") as mock:
        w._template_from_viewer()
        mock.assert_called_once()


def test_delete_from_viewer_no_selection(widget, monkeypatch):
    with patch.object(widget, "_delete_file") as mock:
        widget._delete_from_viewer()
        mock.assert_not_called()


def test_delete_from_viewer_with_selection(populated_widget, monkeypatch):
    w, d = populated_widget
    w.selectRow(0)
    with patch.object(w, "_delete_file") as mock:
        w._delete_from_viewer()
        mock.assert_called_once()


# ---------------------------------------------------------------------------
# _on_double_click
# ---------------------------------------------------------------------------


def test_on_double_click_image(qtbot, base_config, tmp_path, catalog_env):
    from PIL import Image

    f = tmp_path / "img.png"
    Image.new("RGB", (10, 10)).save(str(f))
    config = dict(base_config)
    config["image_extensions"] = [".jpg", ".jpeg", ".png"]
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch.object(w, "_show_image") as mock_show:
        w._on_double_click(0, w._NAME_COL)
        mock_show.assert_called_once()


def test_on_double_click_video(qtbot, base_config, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"fake")
    config = dict(base_config)
    config["video_extensions"] = [".mp4"]
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch("pbpicat.ui.file_list_widget.QDesktopServices") as mock_svc:
        w._on_double_click(0, w._NAME_COL)
        mock_svc.openUrl.assert_called_once()


def test_on_double_click_sidecar_with_sidecars(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    (tmp_path / "img.xmp").write_text("<meta/>")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch("pbpicat.ui.file_list_widget.QDesktopServices") as mock_svc:
        w._on_double_click(0, w._SIDECAR_COL)
        mock_svc.openUrl.assert_called_once()


def test_on_double_click_sidecar_create_new(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch("pbpicat.ui.file_list_widget.QDesktopServices") as mock_svc:
        w._on_double_click(0, w._SIDECAR_COL)
        mock_svc.openUrl.assert_called_once()


def test_on_double_click_out_of_range(widget):
    widget._on_double_click(999, 0)  # no crash


# ---------------------------------------------------------------------------
# _on_selection_changed
# ---------------------------------------------------------------------------


def test_on_selection_changed_no_viewer(widget):
    widget._on_selection_changed()  # no viewer → no crash


def test_on_selection_changed_multiple(populated_widget, catalog_env):
    w, d = populated_widget
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w.selectAll()
    mock_viewer.reset_mock()  # clear calls triggered by selectAll signal
    w._on_selection_changed()
    mock_viewer.show_message.assert_called_once()


def test_on_selection_changed_rebuilding(populated_widget):
    w, d = populated_widget
    w._rebuilding = True
    w._on_selection_changed()  # should return early


# ---------------------------------------------------------------------------
# _on_thumbnail_ready
# ---------------------------------------------------------------------------


def test_on_thumbnail_ready_null_image(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._on_thumbnail_ready(0, QImage())
    from PySide6.QtWidgets import QLabel

    cell = w.cellWidget(0, 0)
    assert isinstance(cell, QLabel)
    assert cell.text() == "?"


def test_on_thumbnail_ready_invalid_row(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._on_thumbnail_ready(999, QImage())  # no crash


# ---------------------------------------------------------------------------
# closeEvent
# ---------------------------------------------------------------------------


def test_close_event(qtbot, base_config, tmp_path):
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.close()


# ---------------------------------------------------------------------------
# Additional coverage: _show_image, _navigate_viewer, contextMenuEvent
# ---------------------------------------------------------------------------


def test_show_image_creates_viewer(qtbot, catalog_env, sample_png, monkeypatch):
    """Cover _show_image (lines 446-454)."""
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    d = sample_png.parent
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(d))
    # Mock ImageViewer to avoid Qt window creation
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    with patch("pbpicat.ui.file_list_widget.ImageViewer", return_value=mock_viewer):
        w._show_image(sample_png)
        mock_viewer.show.assert_called_once()


def test_show_image_reuses_viewer(qtbot, catalog_env, sample_png, monkeypatch):
    """Cover _show_image when viewer already visible (lines 455-458)."""
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w._show_image(sample_png)
    mock_viewer.load_image.assert_called_once_with(sample_png)


def test_navigate_viewer_forward(qtbot, catalog_env, tmp_path):
    """Cover _navigate_viewer (lines 461-471)."""
    from PIL import Image

    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    for name in ["a.png", "b.png"]:
        Image.new("RGB", (1, 1)).save(str(tmp_path / name))
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w.selectRow(0)
    w._navigate_viewer(1)
    assert w.currentIndex().row() == 1


def test_navigate_viewer_no_selection(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w._navigate_viewer(1)  # no crash


def test_on_selection_changed_image(qtbot, catalog_env, sample_png):
    """Cover _on_selection_changed with 1 selected image (lines 482-487)."""
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    d = sample_png.parent
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(d))
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w.selectRow(0)
    w._on_selection_changed()
    mock_viewer.load_image.assert_called()


def test_refresh_preserve_selection(qtbot, catalog_env, tmp_path):
    """Cover _refresh_preserve_selection (lines 199-207)."""
    from PIL import Image

    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    Image.new("RGB", (1, 1)).save(str(tmp_path / "a.png"))
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.selectRow(0)
    w._refresh_preserve_selection()
    # Should re-select the same path
    assert w.rowCount() == 1


def test_populate_table_video(qtbot, catalog_env, tmp_path):
    """Cover video icon branch in _populate_table (line 376-378)."""
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["video_extensions"] = [".mp4"]
    (tmp_path / "clip.mp4").write_bytes(b"fake")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert w.rowCount() == 1


def test_context_menu_open(qtbot, catalog_env, sample_png, monkeypatch):
    """Cover contextMenuEvent with 'Open' action (lines 537-558)."""
    from PySide6.QtGui import QContextMenuEvent

    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    d = sample_png.parent
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(d))
    w.show()
    w.selectRow(0)

    with patch("pbpicat.ui.file_list_widget.open_default"):
        local_pos = w.visualRect(w.model().index(0, 0)).center()
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local_pos, w.viewport().mapToGlobal(local_pos))
        w.contextMenuEvent(event)


def test_context_menu_invalid_row(qtbot, catalog_env, tmp_path, monkeypatch):
    """Cover contextMenuEvent when no valid row (line 539-541)."""
    from PySide6.QtGui import QContextMenuEvent

    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    local_pos = w.rect().center()
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local_pos, w.mapToGlobal(local_pos))
    w.contextMenuEvent(event)


def test_start_drag(qtbot, catalog_env, sample_png, monkeypatch):
    """Cover startDrag (lines 565-572)."""
    from PySide6.QtCore import Qt

    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    d = sample_png.parent
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(d))
    w.selectRow(0)
    with patch("pbpicat.ui.file_list_widget.QDrag") as mock_drag_cls:
        mock_drag = MagicMock()
        mock_drag_cls.return_value = mock_drag
        w.startDrag(Qt.CopyAction)
        mock_drag.exec.assert_called_once()


def test_start_drag_no_selection(qtbot, catalog_env):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    with patch("pbpicat.ui.file_list_widget.QDrag") as mock_drag_cls:
        w.startDrag(0)
        mock_drag_cls.assert_not_called()


def test_mouse_double_click_left(qtbot, catalog_env, sample_png):
    """Cover mouseDoubleClickEvent (lines 561-562)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMouseEvent

    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["image_extensions"] = [".png"]
    d = sample_png.parent
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(d))
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPoint(50, 5),
        w.mapToGlobal(QPoint(50, 5)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    with patch.object(w, "_on_double_click"):
        w.mouseDoubleClickEvent(event)
