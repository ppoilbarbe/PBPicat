"""Tests for src/pbpicat/ui/image_viewer.py."""

from unittest.mock import MagicMock, patch

from PIL import Image
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeySequence, QMouseEvent

from pbpicat.ui.icons import _text_icon, get_icon
from pbpicat.ui.image_viewer import ImageViewer, _ZoomMode


def _get_icon(name, fallback):
    return get_icon(name, text_fallback=fallback)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_text_icon(qapp):
    icon = _text_icon("A")
    assert not icon.isNull()


def test_get_icon_fallback(qapp):
    icon = _get_icon("nonexistent_icon_name_xyz", "X")
    assert not icon.isNull()


def test_get_icon_known_name(qapp):
    icon = _get_icon("zoom_fit", "⊡")
    assert not icon.isNull()


# ---------------------------------------------------------------------------
# ImageViewer construction
# ---------------------------------------------------------------------------


def test_image_viewer_with_valid_image(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer.windowTitle() == "test.png"
    assert not viewer._pixmap.isNull()


def test_image_viewer_with_missing_image(qtbot, catalog_env, tmp_path):
    missing = tmp_path / "missing.png"
    viewer = ImageViewer(missing)
    qtbot.addWidget(viewer)
    assert viewer._pixmap.isNull()


def test_image_viewer_restores_geometry(qtbot, catalog_env, sample_png, monkeypatch):
    """Branch: saved_geom is not None → restoreGeometry is called."""
    fake_geom = b"\x01\x02\x03"
    mock_qs = MagicMock()
    mock_qs.value.return_value = fake_geom
    mock_qs.setValue = MagicMock()
    mock_qs.sync = MagicMock()
    monkeypatch.setattr("pbpicat.ui.image_viewer.app_qsettings", lambda: mock_qs)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)


def test_image_viewer_falls_back_when_restore_geometry_fails(qtbot, catalog_env, sample_png, monkeypatch):
    """A saved but invalid/stale geometry blob (e.g. from a screen configuration that no
    longer exists) makes restoreGeometry() return False — the window must still get the
    75%-of-screen fallback size instead of staying stuck at Qt's tiny default, which was
    the actual bug: only "was something saved" was checked, not "did it actually apply"."""
    mock_qs = MagicMock()
    mock_qs.value.return_value = b"\x01\x02\x03"  # present but not valid saveGeometry() output
    monkeypatch.setattr("pbpicat.ui.image_viewer.app_qsettings", lambda: mock_qs)
    monkeypatch.setattr(ImageViewer, "restoreGeometry", lambda self, geom: False)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    screen = viewer.screen()
    avail = screen.availableGeometry()
    assert viewer.width() == int(avail.width() * 0.75)
    assert viewer.height() == int(avail.height() * 0.75)


def test_image_viewer_no_screen(qtbot, catalog_env, sample_png, monkeypatch):
    """Branch: screen() returns None → fallback resize."""
    mock_qs = MagicMock()
    mock_qs.value.return_value = None
    monkeypatch.setattr("pbpicat.ui.image_viewer.app_qsettings", lambda: mock_qs)
    with patch.object(ImageViewer, "screen", return_value=None):
        with patch.object(ImageViewer, "parent", return_value=None):
            viewer = ImageViewer(sample_png)
            qtbot.addWidget(viewer)


# ---------------------------------------------------------------------------
# load_image
# ---------------------------------------------------------------------------


def test_load_image_null_pixmap(qtbot, catalog_env, sample_png, tmp_path):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.load_image(tmp_path / "nonexistent.png")
    assert viewer._pixmap.isNull()


def test_load_image_small_dimension(qtbot, catalog_env, tmp_path):
    """min_dim < 64 → _zoom_min = 1.0."""
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (10, 10)).save(str(tiny))
    viewer = ImageViewer(tiny)
    qtbot.addWidget(viewer)
    assert viewer._zoom_min == 1.0


# ---------------------------------------------------------------------------
# Zoom modes
# ---------------------------------------------------------------------------


def test_act_fit_window(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_window()
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_act_1to1(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_1to1()
    assert viewer._mode == _ZoomMode.ONE_TO_ONE


def test_act_fit_width(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_width()
    assert viewer._mode == _ZoomMode.FIT_WIDTH


def test_act_fit_height(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_height()
    assert viewer._mode == _ZoomMode.FIT_HEIGHT


def test_act_zoom_in(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_zoom_in()
    assert viewer._mode == _ZoomMode.CUSTOM


def test_act_zoom_out(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_zoom_out()
    assert viewer._mode == _ZoomMode.CUSTOM


def test_apply_custom_clamps_to_max(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png, zoom_max_percent=100)
    qtbot.addWidget(viewer)
    viewer._apply_custom(999.0)
    assert viewer._factor == 1.0


def test_apply_custom_clamps_to_min(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._apply_custom(0.0)
    assert viewer._factor == viewer._zoom_min


def test_current_factor_null_pixmap(qtbot, catalog_env, tmp_path):
    viewer = ImageViewer(tmp_path / "missing.png")
    qtbot.addWidget(viewer)
    assert viewer._current_factor() == 1.0


def test_current_factor_fit_width_zero_width(qtbot, catalog_env, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._mode = _ZoomMode.FIT_WIDTH
    monkeypatch.setattr(viewer._pixmap, "width", lambda: 0)
    assert viewer._current_factor() == 1.0


def test_current_factor_fit_height_zero_height(qtbot, catalog_env, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._mode = _ZoomMode.FIT_HEIGHT
    monkeypatch.setattr(viewer._pixmap, "height", lambda: 0)
    assert viewer._current_factor() == 1.0


def test_current_factor_fit_window_zero_dims(qtbot, catalog_env, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._mode = _ZoomMode.FIT_WINDOW
    monkeypatch.setattr(viewer._pixmap, "width", lambda: 0)
    monkeypatch.setattr(viewer._pixmap, "height", lambda: 0)
    assert viewer._current_factor() == 1.0


def test_apply_zoom_null_pixmap(qtbot, catalog_env, tmp_path):
    viewer = ImageViewer(tmp_path / "missing.png")
    qtbot.addWidget(viewer)
    viewer._apply_zoom()  # should not crash


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def test_navigate_prev_signal(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.navigate_prev, timeout=500):
        viewer.navigate_prev.emit()


def test_navigate_next_signal(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.navigate_next, timeout=500):
        viewer.navigate_next.emit()


def test_open_requested_signal(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.open_requested, timeout=500):
        viewer.open_requested.emit()


def test_delete_requested_signal(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with qtbot.waitSignal(viewer.delete_requested, timeout=500):
        viewer.delete_requested.emit()


# ---------------------------------------------------------------------------
# eventFilter and _zoom_to_point
# ---------------------------------------------------------------------------


def test_event_filter_mouse_press(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(10, 10),
        viewer._label.mapToGlobal(QPoint(10, 10)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, press)
    assert viewer._drag_pos is not None


def test_event_filter_mouse_release(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer._drag_pos = QPoint(5, 5)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPoint(10, 10),
        viewer._label.mapToGlobal(QPoint(10, 10)),
        Qt.LeftButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, release)
    assert viewer._drag_pos is None


def test_event_filter_mouse_move(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer._drag_pos = QPoint(5, 5)
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPoint(15, 15),
        viewer._label.mapToGlobal(QPoint(15, 15)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, move)


def test_event_filter_double_click(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(600, 400)
    dbl = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPoint(50, 50),
        viewer._label.mapToGlobal(QPoint(50, 50)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    viewer.eventFilter(viewer._label, dbl)


def test_event_filter_other_object(qtbot, catalog_env, sample_png):
    from PySide6.QtGui import QKeyEvent

    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    # Pass a non-label object → super().eventFilter is called → returns False
    other_label = viewer._scroll  # a real QObject
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.NoModifier)
    result = viewer.eventFilter(other_label, event)
    assert result is False


def test_zoom_to_point_zero_size(qtbot, catalog_env, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    monkeypatch.setattr(viewer._label, "width", lambda: 0)
    monkeypatch.setattr(viewer._label, "height", lambda: 0)
    viewer._zoom_to_point(QPoint(10, 10))
    assert viewer._mode == _ZoomMode.CUSTOM


# ---------------------------------------------------------------------------
# close / resize / show events
# ---------------------------------------------------------------------------


def test_close_event_saves_geometry(qtbot, catalog_env, sample_png, monkeypatch):
    mock_qs = MagicMock()
    mock_qs.value.return_value = None
    monkeypatch.setattr("pbpicat.ui.image_viewer.app_qsettings", lambda: mock_qs)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.close()
    mock_qs.setValue.assert_any_call("image_viewer/geometry", viewer.saveGeometry())


def test_resize_event_triggers_apply_zoom(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_fit_window()
    viewer.resize(500, 400)  # triggers resizeEvent


def test_show_event_triggers_apply_zoom(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.hide()


def test_get_icon_theme_found(qapp):
    """Cover line 49 (return theme_icon): patch QIcon.fromTheme to return non-null."""
    from unittest.mock import patch

    non_null_icon = _text_icon("T")  # guaranteed non-null
    with patch("pbpicat.ui.icons.QIcon.fromTheme", return_value=non_null_icon):
        icon = _get_icon("zoom_fit", "⊡")
    assert not icon.isNull()


def test_apply_zoom_custom_mode(qtbot, catalog_env, sample_png):
    """Cover CUSTOM mode in _apply_zoom (lines 327-330)."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(400, 300)
    viewer._apply_custom(2.0)  # sets CUSTOM mode and calls _apply_zoom
    assert viewer._mode == _ZoomMode.CUSTOM


def test_current_factor_one_to_one_mode(qtbot, catalog_env, sample_png):
    """Cover lines 308-309: _current_factor returns 1.0 in ONE_TO_ONE mode."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_1to1()  # mode = ONE_TO_ONE
    factor = viewer._current_factor()
    assert factor == 1.0


def test_current_factor_custom_mode(qtbot, catalog_env, sample_png):
    """Cover line 310: _current_factor returns self._factor in CUSTOM mode."""
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._apply_custom(2.0)  # mode = CUSTOM, _factor = 2.0
    factor = viewer._current_factor()
    assert factor == 2.0


# ---------------------------------------------------------------------------
# set_auto_rotate
# ---------------------------------------------------------------------------


def test_set_auto_rotate_same_value_no_reload(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png, auto_rotate=True)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "load_image") as mock_load:
        viewer.set_auto_rotate(True)
    mock_load.assert_not_called()


def test_set_auto_rotate_different_value_reloads(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png, auto_rotate=True)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "load_image") as mock_load:
        viewer.set_auto_rotate(False)
    mock_load.assert_called_once_with(sample_png)


# ---------------------------------------------------------------------------
# Ctrl+Click → _zoom_to_point (lines 400-401, 439-449)
# ---------------------------------------------------------------------------


def test_event_filter_ctrl_click_zooms_to_point(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(600, 400)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(50, 50),
        viewer._label.mapToGlobal(QPoint(50, 50)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.ControlModifier,
    )
    result = viewer.eventFilter(viewer._label, press)
    assert result is True
    assert viewer._mode == _ZoomMode.CUSTOM


def test_event_filter_ctrl_right_click_zooms_out_to_point(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.resize(600, 400)
    viewer._apply_custom(2.0)
    factor_before = viewer._current_factor()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(50, 50),
        viewer._label.mapToGlobal(QPoint(50, 50)),
        Qt.RightButton,
        Qt.RightButton,
        Qt.ControlModifier,
    )
    result = viewer.eventFilter(viewer._label, press)
    assert result is True
    assert viewer._mode == _ZoomMode.CUSTOM
    assert viewer._current_factor() < factor_before


def test_zoom_to_point_zero_size_zoom_out(qtbot, catalog_env, sample_png, monkeypatch):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._apply_custom(2.0)
    factor_before = viewer._current_factor()
    monkeypatch.setattr(viewer._label, "width", lambda: 0)
    monkeypatch.setattr(viewer._label, "height", lambda: 0)
    viewer._zoom_to_point(QPoint(10, 10), direction=-1)
    assert viewer._mode == _ZoomMode.CUSTOM
    assert viewer._current_factor() < factor_before


# ---------------------------------------------------------------------------
# Metadata panel
# ---------------------------------------------------------------------------


def test_metadata_panel_hidden_by_default(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._metadata_btn.isChecked() is False
    assert viewer._metadata_panel.isHidden() is True


def test_metadata_panel_not_loaded_while_hidden(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_panel.load = MagicMock()
    viewer.load_image(sample_png)
    viewer._metadata_panel.load.assert_not_called()


def test_toggling_metadata_button_shows_and_loads_panel(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    assert viewer._metadata_panel.isHidden() is False
    assert "test.png" in viewer._metadata_panel._browser.toPlainText()


def test_unchecking_metadata_button_clears_panel(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    viewer._metadata_btn.setChecked(False)
    assert viewer._metadata_panel.isHidden() is True
    assert viewer._metadata_panel._browser.toPlainText() == ""


def test_load_image_refreshes_visible_metadata_panel(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    viewer.load_image(other)
    assert "other.png" in viewer._metadata_panel._browser.toPlainText()


def test_shortcut_i_toggles_metadata_panel(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._act_toggle_metadata()
    assert viewer._metadata_btn.isChecked() is True


def test_metadata_panel_side_right_by_default(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._splitter.widget(0) is viewer._scroll
    assert viewer._splitter.widget(1) is viewer._metadata_panel


def test_metadata_panel_side_left(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png, metadata_panel_side="left")
    qtbot.addWidget(viewer)
    assert viewer._splitter.widget(0) is viewer._metadata_panel
    assert viewer._splitter.widget(1) is viewer._scroll


def test_set_metadata_panel_side_live_update(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_metadata_panel_side("left")
    assert viewer._splitter.widget(0) is viewer._metadata_panel
    assert viewer._splitter.widget(1) is viewer._scroll


def test_set_metadata_panel_side_noop_when_unchanged(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    splitter = viewer._splitter
    viewer.set_metadata_panel_side("right")
    assert viewer._splitter is splitter
    assert viewer._splitter.widget(0) is viewer._scroll


def test_close_event_saves_metadata_state(qtbot, catalog_env, sample_png, monkeypatch):
    mock_qs = MagicMock()
    mock_qs.value.return_value = None
    monkeypatch.setattr("pbpicat.ui.image_viewer.app_qsettings", lambda: mock_qs)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    viewer.close()
    mock_qs.setValue.assert_any_call("image_viewer/metadata_panel_visible", True)
    mock_qs.setValue.assert_any_call("image_viewer/metadata_splitter_state", viewer._splitter.saveState())


def test_sidecar_extensions_passed_to_metadata_panel(qtbot, catalog_env, tmp_path):
    from PIL import Image as _Image

    image = tmp_path / "photo.png"
    _Image.new("RGB", (5, 5)).save(str(image))
    (tmp_path / "photo.xmp").write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">Hi</rdf:li></rdf:Alt></dc:title>'
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    viewer = ImageViewer(image, sidecar_extensions=[".xmp"])
    qtbot.addWidget(viewer)
    viewer._metadata_btn.setChecked(True)
    text = viewer._metadata_panel._browser.toPlainText()
    assert "photo.xmp" in text


# ---------------------------------------------------------------------------
# display() dispatch / show_video / video mode
# ---------------------------------------------------------------------------


def _video(tmp_path, name="clip.mp4"):
    path = tmp_path / name
    path.write_bytes(b"fake")
    return path


def test_display_dispatches_image(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    with patch.object(viewer, "load_image") as mock_load, patch.object(viewer, "show_video") as mock_video:
        viewer.display(sample_png)
    mock_load.assert_called_once_with(sample_png)
    mock_video.assert_not_called()


def test_display_dispatches_video(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    with patch.object(viewer, "load_image") as mock_load, patch.object(viewer, "show_video") as mock_video:
        viewer.display(video)
    mock_video.assert_called_once_with(video)
    mock_load.assert_not_called()


def test_show_video_enters_video_mode(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)

    assert viewer._video_mode is True
    assert viewer._mode == _ZoomMode.FIT_WINDOW
    assert viewer.current_path == video
    assert viewer.windowTitle() == video.name
    assert not viewer._pixmap.isNull()
    assert viewer._zoom_label.text() == ""
    for btn in viewer._zoom_buttons + viewer._zoom_inout_buttons + viewer._rotate_buttons:
        assert btn.isEnabled() is False
    assert viewer._rotate_auto_btn.isEnabled() is False
    assert viewer._reset_exif_btn.isEnabled() is False


def test_load_image_after_show_video_restores_controls(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer.load_image(sample_png)

    assert viewer._video_mode is False
    for btn in viewer._zoom_buttons + viewer._zoom_inout_buttons + viewer._rotate_buttons:
        assert btn.isEnabled() is True


def test_video_mode_blocks_set_mode(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._act_1to1()
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_mode_allows_set_mode_fit_window(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._act_fit_window()  # same mode, must not be blocked
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_mode_blocks_apply_custom(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._act_zoom_in()
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_mode_blocks_zoom_to_point(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.show_video(video)
    viewer._zoom_to_point(QPoint(10, 10))
    assert viewer._mode == _ZoomMode.FIT_WINDOW


def test_video_extensions_defaults_to_empty(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    assert viewer._video_extensions == set()


# ---------------------------------------------------------------------------
# set_selection / selection-strip navigation
# ---------------------------------------------------------------------------


def test_set_selection_single_hides_strip(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._strip.setVisible(True)  # simulate strip left over from a previous multi-selection
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png])
    mock_display.assert_called_once_with(sample_png)
    assert viewer._strip.isVisible() is False


def test_set_selection_multiple_shows_strip_and_first_file(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png, other])
    mock_display.assert_called_once_with(sample_png)
    assert viewer._strip.isHidden() is False
    assert viewer._selection_index == 0
    assert len(viewer._strip._labels) == 2


def test_set_selection_with_current_displays_and_highlights_it(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png, other], current=other)
    mock_display.assert_called_once_with(other)
    assert viewer._selection_index == 1
    assert viewer._strip.current_index == 1


def test_set_selection_current_not_in_paths_falls_back_to_first(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    unrelated = tmp_path / "unrelated.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.set_selection([sample_png, other], current=unrelated)
    mock_display.assert_called_once_with(sample_png)
    assert viewer._selection_index == 0


def test_selection_next_prev_clamped(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])

    viewer._act_selection_prev()  # already at index 0 → no-op
    assert viewer._selection_index == 0

    viewer._act_selection_next()
    assert viewer._selection_index == 1
    assert viewer.current_path == other

    viewer._act_selection_next()  # already at last index → no-op
    assert viewer._selection_index == 1

    viewer._act_selection_prev()
    assert viewer._selection_index == 0
    assert viewer.current_path == sample_png


def test_selection_next_noop_for_single_file(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png])
    viewer._act_selection_next()
    assert viewer._selection_index == 0


def test_selection_right_shortcut_navigates(qtbot, catalog_env, sample_png, tmp_path):
    from PySide6.QtGui import QShortcut

    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show()
    qtbot.waitActive(viewer)
    viewer.set_selection([sample_png, other])

    shortcuts = [sc for sc in viewer.findChildren(QShortcut) if sc.key() == QKeySequence(Qt.Key.Key_Right)]
    assert len(shortcuts) == 1
    shortcuts[0].activated.emit()

    assert viewer.current_path == other


def test_selection_strip_renders_video_icon(qtbot, catalog_env, sample_png, tmp_path):
    video = _video(tmp_path)
    viewer = ImageViewer(sample_png, video_extensions=[".mp4"])
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, video])
    assert len(viewer._strip._labels) == 2
    assert not viewer._strip._labels[1].pixmap().isNull()


def test_selection_strip_highlights_current_thumbnail(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])

    assert "palette(highlight)" in viewer._strip._labels[0].styleSheet()
    assert "palette(highlight)" not in viewer._strip._labels[1].styleSheet()

    viewer._act_selection_next()
    assert "palette(highlight)" not in viewer._strip._labels[0].styleSheet()
    assert "palette(highlight)" in viewer._strip._labels[1].styleSheet()


def test_clicking_strip_thumbnail_navigates(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])

    viewer._strip._labels[1].clicked.emit()

    assert viewer._selection_index == 1
    assert viewer.current_path == other
    assert "palette(highlight)" in viewer._strip._labels[1].styleSheet()


def test_selection_goto_out_of_range_ignored(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])
    viewer._act_selection_goto(5)
    assert viewer._selection_index == 0
    assert viewer.current_path == sample_png


def test_clickable_label_emits_on_left_click(qtbot, catalog_env):
    from pbpicat.ui.image_viewer import _ClickableLabel

    label = _ClickableLabel()
    qtbot.addWidget(label)
    with qtbot.waitSignal(label.clicked, timeout=500):
        qtbot.mouseClick(label, Qt.LeftButton)


# ---------------------------------------------------------------------------
# refresh_paths (e.g. after an external rotation)
# ---------------------------------------------------------------------------


def test_refresh_paths_reloads_current_single_file(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.refresh_paths({sample_png})
    mock_display.assert_called_once_with(sample_png)


def test_refresh_paths_ignores_unrelated_path(qtbot, catalog_env, sample_png, tmp_path):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    with patch.object(viewer, "display") as mock_display:
        viewer.refresh_paths({tmp_path / "other.png"})
    mock_display.assert_not_called()


def test_refresh_paths_updates_matching_strip_thumbnail(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])  # displays sample_png, index 0

    with patch.object(viewer._strip, "refresh_thumbnail") as mock_refresh:
        viewer.refresh_paths({other})
    mock_refresh.assert_called_once_with(1, other, viewer._video_extensions)


def test_refresh_paths_updates_both_viewport_and_strip_for_displayed_file(qtbot, catalog_env, sample_png, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (5, 5)).save(str(other))
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.set_selection([sample_png, other])  # displays sample_png, index 0

    with (
        patch.object(viewer, "display") as mock_display,
        patch.object(viewer._strip, "refresh_thumbnail") as mock_refresh,
    ):
        viewer.refresh_paths({sample_png})
    mock_display.assert_called_once_with(sample_png)
    mock_refresh.assert_called_once_with(0, sample_png, viewer._video_extensions)


def test_selection_strip_refresh_thumbnail_out_of_range(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer._strip.refresh_thumbnail(0, sample_png, set())  # no labels yet — no crash
