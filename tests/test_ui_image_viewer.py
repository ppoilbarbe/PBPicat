"""Tests for src/pbpicat/ui/image_viewer.py."""

from unittest.mock import MagicMock, patch

from PIL import Image
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QMouseEvent

from pbpicat.ui.image_viewer import ImageViewer, _get_icon, _text_icon, _ZoomMode

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
    monkeypatch.setattr("pbpicat.ui.image_viewer.qsettings", lambda: mock_qs)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)


def test_image_viewer_no_screen(qtbot, catalog_env, sample_png, monkeypatch):
    """Branch: screen() returns None → fallback resize."""
    mock_qs = MagicMock()
    mock_qs.value.return_value = None
    monkeypatch.setattr("pbpicat.ui.image_viewer.qsettings", lambda: mock_qs)
    with patch.object(ImageViewer, "screen", return_value=None):
        with patch.object(ImageViewer, "parent", return_value=None):
            viewer = ImageViewer(sample_png)
            qtbot.addWidget(viewer)


# ---------------------------------------------------------------------------
# load_image / show_message
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


def test_show_message(qtbot, catalog_env, sample_png):
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.show_message("Hello")
    assert viewer._label.text() == "Hello"
    assert viewer._zoom_label.text() == ""


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
    monkeypatch.setattr("pbpicat.ui.image_viewer.qsettings", lambda: mock_qs)
    viewer = ImageViewer(sample_png)
    qtbot.addWidget(viewer)
    viewer.close()
    mock_qs.setValue.assert_called_with("image_viewer/geometry", viewer.saveGeometry())


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
    with patch("pbpicat.ui.image_viewer.QIcon.fromTheme", return_value=non_null_icon):
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
