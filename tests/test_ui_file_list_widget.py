"""Tests for src/pbpicat/ui/file_list_widget.py."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as _PilImage
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMessageBox

import pbpicat.ui.file_list_widget as _flmod
from pbpicat.config import DEFAULTS
from pbpicat.ui.file_list_widget import (
    FileListWidget,
    _format_size,
    _natural_sort_key,
    _SchemaProposalDialog,
    _ThumbnailWorker,
)


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
# _format_size
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024 * 1024 * 1024, "1.0 GB"),
        (1024**4, "1.0 TB"),
    ],
)
def test_format_size(num_bytes, expected):
    assert _format_size(num_bytes) == expected


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
    c["use_trash"] = False
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
    worker.thumbnail_ready.connect(lambda row, path, img, res: emitted.append(row))
    worker.run()
    assert emitted == []


def test_thumbnail_worker_run_cancelled_immediately(tmp_path):
    f = tmp_path / "a.png"
    _img(f)
    worker = _ThumbnailWorker([f], 64, 64, {".jpg"})
    worker._cancelled = True
    emitted = []
    worker.thumbnail_ready.connect(lambda row, path, img, res: emitted.append(row))
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


def test_refresh_and_select_focuses_widget(populated_widget, monkeypatch):
    """The F2 rename shortcut doesn't move focus to the file list beforehand
    (unlike a click, which used to steal it away); refresh_and_select() must
    grab focus itself so arrow-key navigation works from the new row."""
    w, d = populated_widget
    calls = []
    monkeypatch.setattr(type(w), "setFocus", lambda self, *a: calls.append(1))
    w.refresh_and_select(1)
    assert calls
    assert w.currentRow() == 1


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


def test_reconfigure_with_visible_image_viewer(qtbot, catalog_env, tmp_path):
    """reconfigure propagates auto_rotate to a visible image viewer (line 278)."""
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    _img(tmp_path / "img.png")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w.reconfigure(dict(config))
    mock_viewer.set_auto_rotate.assert_called_once()
    mock_viewer.set_metadata_panel_side.assert_called_once()


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
    config["use_trash"] = False
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
    config["use_trash"] = False
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes):
        w._delete_file(f, [])
    assert not f.exists()


# ---------------------------------------------------------------------------
# move_files_to
# ---------------------------------------------------------------------------


def test_move_files_to_moves_file_and_sidecar(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"
    sc = d / "img_001.xmp"
    assert src.exists()
    assert sc.exists()

    w.move_files_to([src], str(dest))

    assert not src.exists()
    assert not sc.exists()
    assert (dest / "img_001.png").exists()
    assert (dest / "img_001.xmp").exists()


def test_move_files_to_removes_row_from_table(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"

    w.move_files_to([src], str(dest))

    assert src not in w.get_all_files()
    assert w.rowCount() == 1


def test_move_files_to_emits_files_moved_signal(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"
    sc = d / "img_001.xmp"

    plans = []
    w.files_moved.connect(plans.append)
    w.move_files_to([src], str(dest))

    assert len(plans) == 1
    pairs = set(plans[0])
    assert (src, dest / "img_001.png") in pairs
    assert (sc, dest / "img_001.xmp") in pairs


def test_move_files_to_same_directory_is_noop(populated_widget):
    w, d = populated_widget
    src = d / "img_001.png"

    plans = []
    w.files_moved.connect(plans.append)
    w.move_files_to([src], str(d))

    assert plans == []
    assert src.exists()


def test_move_files_to_unrelated_path_is_noop(populated_widget, tmp_path):
    w, _d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()

    plans = []
    w.files_moved.connect(plans.append)
    w.move_files_to([tmp_path / "unrelated.png"], str(dest))

    assert plans == []


def test_move_files_to_conflict_shows_error_and_keeps_file(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_002.png"
    (dest / "img_002.png").write_bytes(b"existing")

    with patch.object(QMessageBox, "critical", return_value=None) as mock_crit:
        w.move_files_to([src], str(dest))

    mock_crit.assert_called_once()
    assert src.exists()
    assert src in w.get_all_files()


# ---------------------------------------------------------------------------
# copy_files_to (internal Shift-drag onto the folder tree)
# ---------------------------------------------------------------------------


def test_copy_files_to_copies_file_and_sidecar_keeps_original(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"
    sc = d / "img_001.xmp"

    w.copy_files_to([src], str(dest))

    assert src.exists()  # original kept
    assert sc.exists()
    assert (dest / "img_001.png").exists()
    assert (dest / "img_001.xmp").exists()


def test_copy_files_to_keeps_table_unchanged(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"

    before = w.get_all_files()
    w.copy_files_to([src], str(dest))

    assert w.get_all_files() == before
    assert w.rowCount() == 2


def test_copy_files_to_emits_files_copied_signal(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"
    sc = d / "img_001.xmp"

    plans = []
    w.files_copied.connect(plans.append)
    w.copy_files_to([src], str(dest))

    assert len(plans) == 1
    pairs = set(plans[0])
    assert (src, dest / "img_001.png") in pairs
    assert (sc, dest / "img_001.xmp") in pairs


def test_copy_files_to_same_directory_is_noop(populated_widget):
    w, d = populated_widget
    src = d / "img_001.png"

    plans = []
    w.files_copied.connect(plans.append)
    w.copy_files_to([src], str(d))

    assert plans == []
    assert src.exists()


def test_copy_files_to_unrelated_path_is_noop(populated_widget, tmp_path):
    w, _d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()

    plans = []
    w.files_copied.connect(plans.append)
    w.copy_files_to([tmp_path / "unrelated.png"], str(dest))

    assert plans == []


def test_copy_files_to_conflict_shows_error_and_keeps_original(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_002.png"
    (dest / "img_002.png").write_bytes(b"existing")

    with patch.object(QMessageBox, "critical", return_value=None) as mock_crit:
        w.copy_files_to([src], str(dest))

    mock_crit.assert_called_once()
    assert src.exists()
    assert src in w.get_all_files()


def test_copy_files_to_does_not_emit_files_moved(populated_widget, tmp_path):
    w, d = populated_widget
    dest = tmp_path / "dest"
    dest.mkdir()
    src = d / "img_001.png"

    move_plans = []
    copy_plans = []
    w.files_moved.connect(move_plans.append)
    w.files_copied.connect(copy_plans.append)
    w.copy_files_to([src], str(dest))

    assert move_plans == []
    assert len(copy_plans) == 1


# ---------------------------------------------------------------------------
# move_external_files_to (drag from outside the app, e.g. a file manager)
# ---------------------------------------------------------------------------


def test_move_external_files_to_moves_file_and_sidecar(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)
    sc = external / "outside.xmp"
    sc.write_text("<meta/>")

    w.move_external_files_to([src], str(d))

    assert not src.exists()
    assert not sc.exists()
    assert (d / "outside.png").exists()
    assert (d / "outside.xmp").exists()


def test_move_external_files_to_refreshes_current_dir(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)

    w.move_external_files_to([src], str(d))

    assert (d / "outside.png") in w.get_all_files()


def test_move_external_files_to_other_dir_no_refresh(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)
    other_dest = tmp_path / "other_dest"
    other_dest.mkdir()

    before = w.get_all_files()
    w.move_external_files_to([src], str(other_dest))

    assert (other_dest / "outside.png").exists()
    assert w.get_all_files() == before


def test_move_external_files_to_skips_non_files(populated_widget, tmp_path):
    w, d = populated_widget
    external_dir = tmp_path / "external_dir"
    external_dir.mkdir()
    missing = tmp_path / "does_not_exist.png"

    plans = []
    w.files_moved_external.connect(plans.append)
    w.move_external_files_to([external_dir, missing], str(d))

    assert plans == []
    assert external_dir.exists()


def test_move_external_files_to_same_dir_is_noop(populated_widget, tmp_path):
    w, d = populated_widget
    already_here = d / "already_here.png"
    _img(already_here)

    plans = []
    w.files_moved_external.connect(plans.append)
    w.move_external_files_to([already_here], str(d))

    assert plans == []
    assert already_here.exists()


def test_move_external_files_to_conflict_shows_error(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "img_001.png"  # same name as an existing file in d
    _img(src)

    with patch.object(QMessageBox, "critical", return_value=None) as mock_crit:
        w.move_external_files_to([src], str(d))

    mock_crit.assert_called_once()
    assert src.exists()


def test_move_external_files_to_does_not_emit_files_moved(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)

    internal_plans = []
    external_plans = []
    w.files_moved.connect(internal_plans.append)
    w.files_moved_external.connect(external_plans.append)
    w.move_external_files_to([src], str(d))

    assert internal_plans == []
    assert len(external_plans) == 1


# ---------------------------------------------------------------------------
# copy_external_files_to (drag from outside the app, e.g. a file manager)
# ---------------------------------------------------------------------------


def test_copy_external_files_to_copies_file_and_sidecar_keeps_original(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)
    sc = external / "outside.xmp"
    sc.write_text("<meta/>")

    w.copy_external_files_to([src], str(d))

    assert src.exists()  # original kept
    assert sc.exists()
    assert (d / "outside.png").exists()
    assert (d / "outside.xmp").exists()


def test_copy_external_files_to_refreshes_current_dir(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)

    w.copy_external_files_to([src], str(d))

    assert (d / "outside.png") in w.get_all_files()


def test_copy_external_files_to_other_dir_no_refresh(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)
    other_dest = tmp_path / "other_dest"
    other_dest.mkdir()

    before = w.get_all_files()
    w.copy_external_files_to([src], str(other_dest))

    assert (other_dest / "outside.png").exists()
    assert w.get_all_files() == before


def test_copy_external_files_to_skips_non_files(populated_widget, tmp_path):
    w, d = populated_widget
    external_dir = tmp_path / "external_dir"
    external_dir.mkdir()

    plans = []
    w.files_copied_external.connect(plans.append)
    w.copy_external_files_to([external_dir], str(d))

    assert plans == []


def test_copy_external_files_to_same_dir_is_noop(populated_widget, tmp_path):
    w, d = populated_widget

    plans = []
    w.files_copied_external.connect(plans.append)
    w.copy_external_files_to([d / "img_001.png"], str(d))

    assert plans == []


def test_copy_external_files_to_conflict_shows_error_and_copies_nothing(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "img_001.png"  # same name as an existing file in d
    _img(src)

    with patch.object(QMessageBox, "critical", return_value=None) as mock_crit:
        w.copy_external_files_to([src], str(d))

    mock_crit.assert_called_once()
    assert src.exists()


def test_copy_external_files_to_oserror_shows_warning(populated_widget, tmp_path, monkeypatch):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)

    def mock_copy2(_src, _dst):
        raise OSError("device busy")

    monkeypatch.setattr(shutil, "copy2", mock_copy2)
    with patch.object(QMessageBox, "warning", return_value=None) as mock_warn:
        w.copy_external_files_to([src], str(d))

    mock_warn.assert_called_once()
    assert src.exists()


def test_copy_external_files_to_does_not_emit_other_signals(populated_widget, tmp_path):
    w, d = populated_widget
    external = tmp_path / "external"
    external.mkdir()
    src = external / "outside.png"
    _img(src)

    move_plans = []
    copy_plans = []
    w.files_moved_external.connect(move_plans.append)
    w.files_copied_external.connect(copy_plans.append)
    w.copy_external_files_to([src], str(d))

    assert move_plans == []
    assert len(copy_plans) == 1


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
# _viewer_entry helper
# ---------------------------------------------------------------------------


def test_viewer_entry_no_viewer(widget):
    assert widget._viewer_entry() is None


def test_viewer_entry_no_current_path(populated_widget):
    w, d = populated_widget
    w._image_viewer = MagicMock(current_path=None)
    assert w._viewer_entry() is None


def test_viewer_entry_stale_path(populated_widget):
    w, d = populated_widget
    w._image_viewer = MagicMock(current_path=d / "missing.png")
    assert w._viewer_entry() is None


def test_viewer_entry_match(populated_widget):
    w, d = populated_widget
    path = w._display_data[0][0]
    w._image_viewer = MagicMock(current_path=path)
    entry = w._viewer_entry()
    assert entry is not None
    assert entry[0] == path


# ---------------------------------------------------------------------------
# Viewer helpers (_open_from_viewer, _delete_from_viewer, etc.)
# ---------------------------------------------------------------------------


def test_open_from_viewer_no_selection(widget, monkeypatch):
    with patch("pbpicat.ui.file_list_widget.open_default") as mock:
        widget._open_from_viewer()
        mock.assert_not_called()


def test_open_from_viewer_with_selection(populated_widget, monkeypatch):
    w, d = populated_widget
    w._image_viewer = MagicMock(current_path=w._display_data[0][0])
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
    w._image_viewer = MagicMock(current_path=w._display_data[0][0])
    with patch.object(w, "_propose_schema") as mock:
        w._template_from_viewer()
        mock.assert_called_once()


def test_delete_from_viewer_no_selection(widget, monkeypatch):
    with patch.object(widget, "_delete_file") as mock:
        widget._delete_from_viewer()
        mock.assert_not_called()


def test_delete_from_viewer_with_selection(populated_widget, monkeypatch):
    w, d = populated_widget
    w._image_viewer = MagicMock(current_path=w._display_data[0][0])
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
    with patch.object(w, "_show_in_viewer") as mock_show:
        w._on_double_click(0, w._NAME_COL)
        mock_show.assert_called_once_with(f, selection=[f])


def test_on_double_click_video(qtbot, base_config, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"fake")
    config = dict(base_config)
    config["video_extensions"] = [".mp4"]
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch.object(w, "_show_in_viewer") as mock_show:
        w._on_double_click(0, w._NAME_COL)
        mock_show.assert_called_once_with(f, selection=[])


def test_on_double_click_sidecar_with_sidecars(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    (tmp_path / "img.xmp").write_text("<meta/>")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch("pbpicat.ui.file_list_widget.open_default") as mock_open:
        w._on_double_click(0, w._SIDECAR_COL)
        mock_open.assert_called_once()


def test_on_double_click_sidecar_create_new(qtbot, base_config, tmp_path):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    with patch("pbpicat.ui.file_list_widget.open_default") as mock_open:
        w._on_double_click(0, w._SIDECAR_COL)
        mock_open.assert_called_once()


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
    mock_viewer.set_selection.assert_called_once_with(w.get_selected_files())


def test_on_selection_changed_rebuilding(populated_widget):
    w, d = populated_widget
    w._rebuilding = True
    w._on_selection_changed()  # should return early


# ---------------------------------------------------------------------------
# _on_thumbnail_ready
# ---------------------------------------------------------------------------


def test_on_thumbnail_ready_null_image(qtbot, base_config, tmp_path):
    p = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._on_thumbnail_ready(0, p, QImage(), QSize())
    from PySide6.QtWidgets import QLabel

    cell = w.cellWidget(0, 0)
    assert isinstance(cell, QLabel)
    assert cell.text() == "?"


def test_on_thumbnail_ready_invalid_row(qtbot, base_config, tmp_path):
    p = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._on_thumbnail_ready(999, p, QImage(), QSize())  # no crash


def test_on_thumbnail_ready_adds_resolution_to_name_cell(qtbot, base_config, tmp_path):
    p = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._on_thumbnail_ready(0, p, QImage(), QSize(1920, 1080))
    assert "1920×1080" in w.item(0, w._NAME_COL).text()


def test_on_thumbnail_ready_invalid_resolution_leaves_name_cell_unchanged(qtbot, base_config, tmp_path):
    p = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    before = w.item(0, w._NAME_COL).text()
    w._on_thumbnail_ready(0, p, QImage(), QSize())  # invalid size: not found yet
    assert w.item(0, w._NAME_COL).text() == before


def test_on_thumbnail_ready_stale_path_ignored(qtbot, base_config, tmp_path):
    """A signal for a path that no longer matches the row (stale, from a cancelled
    worker after a directory/catalog switch) must be dropped, not painted."""
    p = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    before = w.item(0, w._NAME_COL).text()
    stale_path = tmp_path / "does_not_match.png"
    w._on_thumbnail_ready(0, stale_path, QImage(), QSize(1920, 1080))
    assert w.item(0, w._NAME_COL).text() == before
    assert stale_path not in w._thumb_loaded
    assert p not in w._thumb_loaded


# ---------------------------------------------------------------------------
# _update_name_cell
# ---------------------------------------------------------------------------


def test_populate_table_name_cell_has_filename_and_size(qtbot, base_config, tmp_path):
    """Right after a directory load, the Name cell shows the file name plus its
    human-readable size on a second line (resolution is added later, once the
    thumbnail worker reports it)."""
    f = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    text = w.item(0, w._NAME_COL).text()
    lines = text.split("\n")
    assert lines[0] == "img.png"
    assert lines[1] == _format_size(f.stat().st_size)


def test_update_name_cell_with_resolution(qtbot, base_config, tmp_path):
    f = _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w._update_name_cell(0, f, resolution=QSize(640, 480))
    text = w.item(0, w._NAME_COL).text()
    assert text == f"img.png\n640×480  ·  {_format_size(f.stat().st_size)}"


# ---------------------------------------------------------------------------
# closeEvent
# ---------------------------------------------------------------------------


def test_close_event(qtbot, base_config, tmp_path):
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.close()


# ---------------------------------------------------------------------------
# Additional coverage: _show_in_viewer, _navigate_viewer, contextMenuEvent
# ---------------------------------------------------------------------------


def test_show_in_viewer_creates_viewer(qtbot, catalog_env, sample_png, monkeypatch):
    """Cover _show_in_viewer (lines 446-454)."""
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
    with patch("pbpicat.ui.file_list_widget.ImageViewer", return_value=mock_viewer) as mock_cls:
        w._show_in_viewer(sample_png)
        mock_viewer.show.assert_called_once()
        _args, kwargs = mock_cls.call_args
        assert kwargs["sidecar_extensions"] == config["sidecar_extensions"]
        assert kwargs["metadata_panel_side"] == config["metadata_panel_side"]
        assert kwargs["video_extensions"] == list(w._video_exts)


def test_show_in_viewer_reuses_viewer(qtbot, catalog_env, sample_png, monkeypatch):
    """Cover _show_in_viewer when viewer already visible (lines 455-458)."""
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w._show_in_viewer(sample_png)
    mock_viewer.display.assert_called_once_with(sample_png)


def test_show_in_viewer_reuses_viewer_for_video(qtbot, base_config, tmp_path):
    """Double-clicking a video while the viewer is already open must reuse it (display(),
    not load_image() — which would try to decode the video as an image)."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    config = dict(base_config)
    config["video_extensions"] = [".mp4"]
    w = FileListWidget(config)
    qtbot.addWidget(w)
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w._show_in_viewer(video)
    mock_viewer.display.assert_called_once_with(video)
    mock_viewer.load_image.assert_not_called()


def test_show_in_viewer_shift_double_click_keeps_selection_strip(populated_widget):
    """Shift+double-click keeps the table's multi-row selection — the viewer must show
    the full selection strip with the double-clicked file as the one displayed, not
    silently drop back to single-file mode."""
    w, d = populated_widget
    paths = [p for p, _ in w._display_data]
    assert len(paths) >= 2
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w._show_in_viewer(paths[1], selection=paths)
    mock_viewer.set_selection.assert_called_once_with(paths, current=paths[1])
    mock_viewer.display.assert_not_called()


def test_show_in_viewer_creates_viewer_with_selection_strip(qtbot, catalog_env, sample_png, monkeypatch, tmp_path):
    """Same as above but for the branch that constructs a brand-new ImageViewer
    (no viewer open yet when the Shift+double-click happens)."""
    other = tmp_path / "other.png"
    from PIL import Image as _Image

    _Image.new("RGB", (5, 5)).save(str(other))
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    w = FileListWidget(config)
    qtbot.addWidget(w)
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    with patch("pbpicat.ui.file_list_widget.ImageViewer", return_value=mock_viewer):
        w._show_in_viewer(sample_png, selection=[sample_png, other])
    mock_viewer.set_selection.assert_called_once_with([sample_png, other], current=sample_png)


def test_show_in_viewer_single_selection_does_not_call_set_selection(qtbot, catalog_env, sample_png):
    """A plain double-click (selection == [path]) must not open the strip."""
    w = FileListWidget(dict(DEFAULTS))
    qtbot.addWidget(w)
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w._show_in_viewer(sample_png, selection=[sample_png])
    mock_viewer.display.assert_called_once_with(sample_png)
    mock_viewer.set_selection.assert_not_called()


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
    mock_viewer.set_selection.assert_called_once_with([sample_png])


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


def test_start_drag_supports_both_actions_move_default(qtbot, catalog_env, sample_png):
    """Both Copy and Move are offered so Qt's native drag loop live-tracks Ctrl/Shift and
    updates the cursor itself; Move is the default when no modifier is held (Qt's own
    Ctrl=copy/Shift=move mapping isn't overridable from application code)."""
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
        w.startDrag(Qt.MoveAction)
        mock_drag.exec.assert_called_once_with(Qt.CopyAction | Qt.MoveAction, Qt.MoveAction)
        assert mock_drag.setDragCursor.call_count == 3
        actions = [call.args[1] for call in mock_drag.setDragCursor.call_args_list]
        assert actions == [Qt.CopyAction, Qt.MoveAction, Qt.IgnoreAction]


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


# ---------------------------------------------------------------------------
# Bug regression: refresh_and_select_paths — multi-select preserved after undo
# ---------------------------------------------------------------------------


def test_refresh_and_select_paths_selects_multiple(qtbot, base_config, tmp_path):
    """All paths in the set must be selected after refresh_and_select_paths."""
    _img(tmp_path / "a.png")
    _img(tmp_path / "b.png")
    _img(tmp_path / "c.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))

    paths = {tmp_path / "a.png", tmp_path / "c.png"}
    w.refresh_and_select_paths(paths)

    selected = set(w.get_selected_files())
    assert selected == paths
    assert w.currentRow() == 0  # not just visually selected — current index must follow too


def test_refresh_and_select_paths_stops_debounce(qtbot, base_config, tmp_path):
    """The debounce timer must be inactive after refresh_and_select_paths."""
    _img(tmp_path / "a.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))

    w._refresh_debounce.start()
    assert w._refresh_debounce.isActive()

    w.refresh_and_select_paths({tmp_path / "a.png"})
    assert not w._refresh_debounce.isActive()


def test_refresh_preserve_selection_multi(qtbot, base_config, tmp_path):
    """_refresh_preserve_selection must restore all previously selected rows."""
    _img(tmp_path / "a.png")
    _img(tmp_path / "b.png")
    _img(tmp_path / "c.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))

    # Select two files manually (bypass auto_selecting guard)
    from PySide6.QtCore import QItemSelectionModel

    sm = w.selectionModel()
    sm.select(w.model().index(0, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    sm.select(w.model().index(2, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)

    w._refresh_preserve_selection()

    selected = set(w.get_selected_files())
    assert selected == {tmp_path / "a.png", tmp_path / "c.png"}
    assert w.currentRow() == 0  # not just visually selected — current index must follow too


def test_refresh_preserve_selection_sets_current_row(qtbot, base_config, tmp_path):
    """Regression: a file-system-watcher-triggered refresh mid-way through a rename
    left currentIndex() invalid (-1) even though the row was visibly re-selected,
    which made the next arrow-key press jump to row 0 instead of continuing from
    the selected row (reported bug: F2-triggered rename, then arrow key)."""
    _img(tmp_path / "a.png")
    _img(tmp_path / "b.png")
    _img(tmp_path / "c.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))

    w.selectRow(2)
    assert w.currentRow() == 2

    w._refresh_preserve_selection()

    assert w.currentRow() == 2
    assert set(w.get_selected_files()) == {tmp_path / "c.png"}


# ---------------------------------------------------------------------------
# Bug regression: viewer not updated during load_directory / focusInEvent
# ---------------------------------------------------------------------------


def test_load_directory_selects_first_image_and_updates_open_viewer(qtbot, base_config, tmp_path):
    """load_directory auto-selects the first image; an already-open viewer follows it."""
    _img(tmp_path / "a.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)

    viewer = MagicMock()
    viewer.isVisible.return_value = True
    w._image_viewer = viewer

    w.load_directory(str(tmp_path))

    viewer.set_selection.assert_called_once_with([tmp_path / "a.png"])


def test_focus_in_event_does_not_trigger_viewer(qtbot, base_config, tmp_path):
    """focusInEvent must not auto-select (or touch the viewer) while the image viewer is visible."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent

    _img(tmp_path / "a.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.clearSelection()

    viewer = MagicMock()
    viewer.isVisible.return_value = True
    w._image_viewer = viewer

    event = QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason)
    w.focusInEvent(event)

    assert len(w.selectedIndexes()) == 0  # auto-select skipped while viewer is visible
    viewer.set_selection.assert_not_called()


def test_focus_in_event_mouse_does_not_auto_select(qtbot, base_config, tmp_path):
    """Mouse-triggered focus must not auto-select row 0 (the click handles selection)."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent

    _img(tmp_path / "a.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.clearSelection()

    viewer = MagicMock()
    viewer.isVisible.return_value = True
    w._image_viewer = viewer

    event = QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason)
    w.focusInEvent(event)

    assert len(w.selectedIndexes()) == 0  # no auto-select: the click will handle it
    viewer.set_selection.assert_not_called()


# ---------------------------------------------------------------------------
# _ThumbnailWorker: branch that actually loads an image (lines 107-108)
# ---------------------------------------------------------------------------


def test_thumbnail_worker_run_loads_image(tmp_path):
    f = tmp_path / "img.png"
    _img(f)
    worker = _ThumbnailWorker([f], 64, 64, {".png"})
    emitted = []
    worker.thumbnail_ready.connect(lambda row, path, img, res: emitted.append((row, path, img)))
    worker.run()
    assert len(emitted) == 1
    assert emitted[0][0] == 0
    assert emitted[0][1] == f
    assert not emitted[0][2].isNull()


def test_thumbnail_worker_run_with_explicit_rows(tmp_path):
    f = tmp_path / "img.png"
    _img(f)
    worker = _ThumbnailWorker([f], 64, 64, {".png"}, rows=[5])
    emitted = []
    worker.thumbnail_ready.connect(lambda row, path, img, res: emitted.append(row))
    worker.run()
    assert emitted == [5]


# ---------------------------------------------------------------------------
# load_directory: remove old watched path when called twice (line 224)
# ---------------------------------------------------------------------------


def test_load_directory_twice_removes_old_watch(qtbot, base_config, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert str(tmp_path) in w._watcher.directories()
    w.load_directory(str(sub))
    assert str(sub) in w._watcher.directories()
    assert str(tmp_path) not in w._watcher.directories()


# ---------------------------------------------------------------------------
# _on_dir_changed_on_disk: starts debounce timer (line 234)
# ---------------------------------------------------------------------------


def test_on_dir_changed_on_disk_starts_debounce(populated_widget):
    w, _ = populated_widget
    assert not w._refresh_debounce.isActive()
    w._on_dir_changed_on_disk()
    assert w._refresh_debounce.isActive()
    w._refresh_debounce.stop()


# ---------------------------------------------------------------------------
# refresh_thumbnails_for_paths: image found → loop body + worker start (350-355, 358-362)
# ---------------------------------------------------------------------------


def test_refresh_thumbnails_for_paths_with_image(qtbot, base_config, tmp_path, monkeypatch):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    # Prevent the worker thread from actually starting
    monkeypatch.setattr(_ThumbnailWorker, "start", lambda self: None)
    w.refresh_thumbnails_for_paths({tmp_path / "img.png"})
    assert w._worker is not None


def test_refresh_thumbnails_for_paths_no_match(qtbot, base_config, tmp_path, monkeypatch):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.refresh_thumbnails_for_paths({tmp_path / "other.png"})  # path not in display_data
    assert w._worker is None


def test_refresh_thumbnails_for_paths_delegates_to_open_viewer(qtbot, base_config, tmp_path, monkeypatch):
    """Rotating a file must let an open viewer refresh anything it shows for it —
    the main viewport and/or a matching thumbnail in its selection strip — which
    ImageViewer.refresh_paths() itself decides based on what it's currently showing."""
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    monkeypatch.setattr(_ThumbnailWorker, "start", lambda self: None)

    viewer = MagicMock()
    viewer.isVisible.return_value = True
    w._image_viewer = viewer

    w.refresh_thumbnails_for_paths({tmp_path / "img.png"})

    viewer.refresh_paths.assert_called_once_with({tmp_path / "img.png"})


def test_refresh_thumbnails_for_paths_no_open_viewer(qtbot, base_config, tmp_path, monkeypatch):
    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    monkeypatch.setattr(_ThumbnailWorker, "start", lambda self: None)

    w.refresh_thumbnails_for_paths({tmp_path / "img.png"})  # no crash without a viewer


# ---------------------------------------------------------------------------
# _scan_directory: OSError when unlinking empty sidecar (lines 390-391)
# ---------------------------------------------------------------------------


def test_scan_directory_empty_sidecar_unlink_oserror(qtbot, catalog_env, tmp_path, monkeypatch):
    config = dict(DEFAULTS)
    config["delete_empty_sidecars"] = True
    config["confirm_deletions"] = False
    _img(tmp_path / "img.png")
    empty_sc = tmp_path / "img.xmp"
    empty_sc.write_bytes(b"")

    orig_unlink = Path.unlink

    def fail_xmp_unlink(self, missing_ok=False):
        if self.suffix == ".xmp":
            raise OSError("locked")
        orig_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_xmp_unlink)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    assert empty_sc.exists()  # OSError was silenced; file untouched


# ---------------------------------------------------------------------------
# _navigate_viewer: video files are navigable (ImageViewer can display them)
# ---------------------------------------------------------------------------


def test_navigate_viewer_reaches_video(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["video_extensions"] = [".mp4"]
    _img(tmp_path / "a.png")
    (tmp_path / "b.mp4").write_bytes(b"fake")
    _img(tmp_path / "c.png")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    mock_viewer = MagicMock()
    mock_viewer.isVisible.return_value = True
    w._image_viewer = mock_viewer
    w.selectRow(0)  # a.png
    w._navigate_viewer(+1)  # lands on b.mp4 — no longer skipped
    assert w.get_selected_files()[0].name == "b.mp4"


# ---------------------------------------------------------------------------
# viewportEvent: ToolTip on NAME_COL shows preview (lines 582-590)
# ---------------------------------------------------------------------------


def test_viewport_event_tooltip_shows_preview(qtbot, base_config, tmp_path, monkeypatch):
    from PySide6.QtCore import QEvent, QPoint

    _img(tmp_path / "img.png")
    w = FileListWidget(base_config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_schema_getter(lambda: ["Nature", "Birds", "", "", "", ""])

    # Aim at the NAME_COL item of row 0 regardless of widget geometry
    monkeypatch.setattr(w, "itemAt", lambda pos: w.item(0, w._NAME_COL))

    event = MagicMock()
    event.type.return_value = QEvent.Type.ToolTip
    event.pos.return_value = QPoint(0, 0)
    event.globalPos.return_value = QPoint(0, 0)

    result = w.viewportEvent(event)
    assert result is True


# ---------------------------------------------------------------------------
# _compute_preview_name: video marker branch (lines 600-603)
# ---------------------------------------------------------------------------


def test_compute_preview_name_video_branch(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["video_extensions"] = [".mp4"]
    config["video_marker"] = "VID"
    (tmp_path / "clip.mp4").write_bytes(b"fake")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.set_schema_getter(lambda: ["Nature", "", "", "", "", ""])
    w.set_video_marker_pos_getter(lambda: 1)
    result = w._compute_preview_name(tmp_path / "clip.mp4")
    assert "VID" in result


# ---------------------------------------------------------------------------
# keyPressEvent: else branch for unhandled keys (line 631)
# ---------------------------------------------------------------------------


def test_keypressevent_other_key(populated_widget, qtbot):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    w, _ = populated_widget
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Space, Qt.NoModifier)
    w.keyPressEvent(event)  # no crash; falls through to super()


# ---------------------------------------------------------------------------
# contextMenuEvent: select row when not in selection (line 641)
# ---------------------------------------------------------------------------


def test_context_menu_selects_unselected_row(populated_widget, monkeypatch):
    from PySide6.QtCore import QPoint

    w, _ = populated_widget
    w.clearSelection()
    monkeypatch.setattr(w, "rowAt", lambda y: 0)

    event = MagicMock()
    event.globalPos.return_value = QPoint(100, 10)
    event.ignore = MagicMock()
    event.accept = MagicMock()

    w.contextMenuEvent(event)

    assert w.get_selected_files()
    event.accept.assert_called_once()


# ---------------------------------------------------------------------------
# contextMenuEvent: ctx_actions and rotation_actions added (lines 644-649, 651-653)
# ---------------------------------------------------------------------------


def test_context_menu_with_all_actions(populated_widget, mock_qmenu, monkeypatch):
    from PySide6.QtCore import QPoint

    w, _ = populated_widget
    open_act = MagicMock()
    open_with_act = MagicMock()
    template_act = MagicMock()
    delete_act = MagicMock()
    w.set_context_actions(open_act, open_with_act, template_act, delete_act)
    w.set_rotation_actions(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

    w.selectRow(0)
    monkeypatch.setattr(w, "rowAt", lambda y: 0)

    event = MagicMock()
    event.globalPos.return_value = QPoint(100, 10)
    event.ignore = MagicMock()
    event.accept = MagicMock()

    w.contextMenuEvent(event)

    mock_qmenu.addAction.assert_called()
    event.accept.assert_called_once()


# ---------------------------------------------------------------------------
# _open_with_from_viewer: with selection (line 694)
# ---------------------------------------------------------------------------


def test_open_with_from_viewer_with_selection(populated_widget):
    w, _ = populated_widget
    w._image_viewer = MagicMock(current_path=w._display_data[0][0])
    with patch("pbpicat.ui.file_list_widget.open_with") as mock_open:
        w._open_with_from_viewer()
    mock_open.assert_called_once()


# ---------------------------------------------------------------------------
# _rotate_from_viewer: with selection and callback (lines 702-704)
# ---------------------------------------------------------------------------


def test_rotate_from_viewer_with_selection(populated_widget):
    w, _ = populated_widget
    w._image_viewer = MagicMock(current_path=w._display_data[0][0])
    callback = MagicMock()
    w.set_rotate_callback(callback)
    w._rotate_from_viewer(90)
    callback.assert_called_once()


# ---------------------------------------------------------------------------
# _delete_file: count message when all_files > delete_list_max_files (line 727)
# ---------------------------------------------------------------------------


def test_delete_file_count_message_when_many(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = True
    config["delete_list_max_files"] = 1
    config["delete_empty_sidecars"] = False
    config["use_trash"] = False
    for i in range(3):
        _img(tmp_path / f"img_{i:03d}.png")
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.selectAll()  # 3 selected → to_delete has 3 entries → len > 1

    with patch.object(QMessageBox, "exec", return_value=QMessageBox.No):
        w._delete_file(w._display_data[0][0], [])

    assert all((tmp_path / f"img_{i:03d}.png").exists() for i in range(3))


# ---------------------------------------------------------------------------
# _remove_empty_parents: OSError from rmdir (lines 765-766)
# ---------------------------------------------------------------------------


def test_remove_empty_parents_oserror(populated_widget, monkeypatch):
    w, tmp_path = populated_widget
    empty = tmp_path / "empty_sub"
    empty.mkdir()

    def fail_rmdir(self):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "rmdir", fail_rmdir)
    w._remove_empty_parents(empty)  # must not raise
    assert empty.exists()


# ---------------------------------------------------------------------------
# _propose_schema: info dialog when no match (lines 769-778)
# and schema dialog accepted (lines 779-784)
# ---------------------------------------------------------------------------


def test_propose_schema_no_match_shows_info(populated_widget):
    w, tmp_path = populated_widget
    # No history → _infer_schema returns None
    with patch.object(QMessageBox, "information", return_value=None) as mock_info:
        w._propose_schema(tmp_path / "img_001.png")
    mock_info.assert_called_once()


def test_propose_schema_dialog_accepted_emits_signal(populated_widget, monkeypatch):
    from PySide6.QtWidgets import QDialog

    w, tmp_path = populated_widget
    monkeypatch.setattr(w, "_infer_schema", lambda p: ["Nature", "Birds", "", "", "", ""])

    received = []
    w.schema_proposed.connect(lambda fields: received.append(fields))

    with patch.object(_SchemaProposalDialog, "exec", return_value=QDialog.Accepted):
        w._propose_schema(tmp_path / "img_001.png")

    assert received == [["Nature", "Birds", "", "", "", ""]]


def test_propose_schema_dialog_rejected(populated_widget, monkeypatch):
    from PySide6.QtWidgets import QDialog

    w, tmp_path = populated_widget
    monkeypatch.setattr(w, "_infer_schema", lambda p: ["Nature", "Birds", "", "", "", ""])

    received = []
    w.schema_proposed.connect(lambda fields: received.append(fields))

    with patch.object(_SchemaProposalDialog, "exec", return_value=QDialog.Rejected):
        w._propose_schema(tmp_path / "img_001.png")

    assert received == []


# ---------------------------------------------------------------------------
# Private wrapper methods: _open_selection, _open_with_selection,
# _open_file, _open_file_with (lines 869, 872, 875, 878)
# ---------------------------------------------------------------------------


def test_private_open_wrappers(populated_widget):
    w, tmp_path = populated_widget
    w.selectRow(0)

    with (
        patch("pbpicat.ui.file_list_widget.open_default") as mock_def,
        patch("pbpicat.ui.file_list_widget.open_with") as mock_with,
    ):
        w._open_selection()
        w._open_with_selection()
        w._open_file(tmp_path / "img_001.png")
        w._open_file_with(tmp_path / "img_001.png")

    assert mock_def.call_count == 2  # _open_selection + _open_file
    assert mock_with.call_count == 2  # _open_with_selection + _open_file_with


# ---------------------------------------------------------------------------
# use_trash mode
# ---------------------------------------------------------------------------


def test_use_trash_calls_move_to_trash(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["use_trash"] = True
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.selectRow(0)

    with patch("pbpicat.ui.file_list_widget.QFile.moveToTrash", return_value=True) as mock_trash:
        w._delete_file(f, [])

    mock_trash.assert_called_once_with(str(f))


def test_use_trash_error_shows_warning(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = False
    config["delete_empty_sidecars"] = False
    config["use_trash"] = True
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))
    w.selectRow(0)

    with (
        patch("pbpicat.ui.file_list_widget.QFile.moveToTrash", return_value=False),
        patch.object(QMessageBox, "warning", return_value=None) as mock_warn,
    ):
        w._delete_file(f, [])

    mock_warn.assert_called_once()


def test_use_trash_confirmation_message(qtbot, catalog_env, tmp_path):
    config = dict(DEFAULTS)
    config["confirm_deletions"] = True
    config["delete_empty_sidecars"] = False
    config["use_trash"] = True
    f = tmp_path / "img.png"
    _img(f)
    w = FileListWidget(config)
    qtbot.addWidget(w)
    w.load_directory(str(tmp_path))

    with (
        patch.object(QMessageBox, "setText") as mock_set_text,
        patch.object(QMessageBox, "exec", return_value=QMessageBox.No),
    ):
        w._delete_file(f, [])

    assert mock_set_text.call_args is not None
    assert "trash" in mock_set_text.call_args[0][0].lower()
