from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pbpicat.config import DEFAULTS, app_qsettings
from pbpicat.image_io import load_pixmap

from .icons import ICON_SIZE as _ICON_SIZE
from .icons import get_icon
from .metadata_panel import MetadataPanel

_METADATA_PANEL_DEFAULT_WIDTH = 320


class _ZoomMode(Enum):
    FIT_WINDOW = auto()
    FIT_WIDTH = auto()
    FIT_HEIGHT = auto()
    ONE_TO_ONE = auto()
    CUSTOM = auto()


class ImageViewer(QWidget):
    """
    Non-modal independent image viewer with zoom toolbar.

    Zoom modes (toolbar, left to right):
      1:1  |  Zoom in  |  Zoom out  |  Width  |  Height  |  Window (default)
    """

    navigate_prev = Signal()
    navigate_next = Signal()
    open_requested = Signal()
    open_with_requested = Signal()
    template_requested = Signal()
    delete_requested = Signal()
    rotate_requested = Signal(object)  # int (90, -90, 180) or "auto"

    def __init__(
        self,
        image_path: Path,
        parent=None,
        zoom_step_percent: int = DEFAULTS["zoom_step_percent"],
        zoom_max_percent: int = DEFAULTS["zoom_max_percent"],
        auto_rotate: bool = True,
        sidecar_extensions: list[str] | None = None,
        metadata_panel_side: str = DEFAULTS["metadata_panel_side"],
    ):
        super().__init__(parent, Qt.Window)
        self.setMinimumSize(300, 200)

        self._zoom_step = zoom_step_percent / 100.0
        self._zoom_max = zoom_max_percent / 100.0
        self._mode = _ZoomMode.FIT_WINDOW
        self._factor = 1.0  # used only in CUSTOM mode
        self._zoom_min = 0.01
        self._drag_pos: QPoint | None = None
        self._rotate_auto_btn: QToolButton | None = None
        self._reset_exif_btn: QToolButton | None = None
        self._metadata_btn: QToolButton | None = None
        self._auto_rotate = auto_rotate
        self._current_path: Path | None = None
        self._sidecar_extensions = sidecar_extensions or []
        self._metadata_side = metadata_panel_side

        self._setup_ui()
        self._setup_shortcuts()

        saved_geom = app_qsettings().value("image_viewer/geometry")
        if saved_geom:
            self.restoreGeometry(saved_geom)
        saved_splitter = app_qsettings().value("image_viewer/metadata_splitter_state")
        if saved_splitter:
            self._splitter.restoreState(saved_splitter)
        visible = bool(app_qsettings().value("image_viewer/metadata_panel_visible", False, type=bool))
        self._metadata_btn.setChecked(visible)

        self.load_image(image_path)

        if not saved_geom:
            screen = self.screen() or (parent.screen() if parent else None)
            if screen:
                avail = screen.availableGeometry()
                self.resize(int(avail.width() * 0.75), int(avail.height() * 0.75))
            else:
                self.resize(1000, 700)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        root.addLayout(self._build_toolbar())

        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setWidgetResizable(False)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._label.installEventFilter(self)
        self._scroll.setWidget(self._label)

        self._metadata_panel = MetadataPanel()
        self._metadata_panel.setVisible(False)

        self._splitter = QSplitter(Qt.Horizontal)
        self._place_metadata_panel(self._metadata_side)
        root.addWidget(self._splitter, stretch=1)

    def _build_toolbar(self) -> QHBoxLayout:
        tb = QHBoxLayout()
        tb.setSpacing(2)

        specs = [
            ("zoom-fit", "⊡", _("Fit window  0 / X"), self._act_fit_window),
            ("zoom-original", "1:1", _("Actual size (1:1)  1 / Z"), self._act_1to1),
            ("zoom-width", "↔", _("Fit width  W"), self._act_fit_width),
            ("zoom-height", "↕", _("Fit height  H"), self._act_fit_height),
        ]

        self._zoom_buttons: list[QToolButton] = []
        for icon_name, fallback, tip, slot in specs:
            btn = QToolButton()
            btn.setIcon(get_icon(icon_name, text_fallback=fallback))
            btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, s=slot: s())
            tb.addWidget(btn)
            self._zoom_buttons.append(btn)

        # The "fit window" button is active by default
        self._zoom_buttons[0].setChecked(True)

        # Separator between mode buttons and zoom in/out
        sep = QToolButton()
        sep.setEnabled(False)
        sep.setFixedWidth(8)
        tb.addWidget(sep)

        for icon_name, fallback, tip, slot in [
            ("zoom-in", "＋", _("Zoom in  +"), self._act_zoom_in),
            ("zoom-out", "－", _("Zoom out  −"), self._act_zoom_out),
        ]:
            btn = QToolButton()
            btn.setIcon(get_icon(icon_name, text_fallback=fallback))
            btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            tb.addWidget(btn)

        sep2 = QToolButton()
        sep2.setEnabled(False)
        sep2.setFixedWidth(8)
        tb.addWidget(sep2)

        for icon_name, fallback, tip, callback in [
            ("object-rotate-left", "↺", _("Rotate 90° CCW"), lambda: self.rotate_requested.emit(-90)),
            ("object-rotate-right", "↻", _("Rotate 90° CW"), lambda: self.rotate_requested.emit(90)),
            ("object-flip-vertical", "↕", _("Rotate 180°"), lambda: self.rotate_requested.emit(180)),
        ]:
            btn = QToolButton()
            btn.setIcon(get_icon(icon_name, text_fallback=fallback))
            btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
            btn.setToolTip(tip)
            btn.clicked.connect(callback)
            tb.addWidget(btn)

        self._rotate_auto_btn = QToolButton()
        self._rotate_auto_btn.setIcon(get_icon("auto-rotate", text_fallback="EXIF"))
        self._rotate_auto_btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self._rotate_auto_btn.setToolTip(_("Apply EXIF orientation"))
        self._rotate_auto_btn.clicked.connect(lambda: self.rotate_requested.emit("auto"))
        self._rotate_auto_btn.setEnabled(False)
        tb.addWidget(self._rotate_auto_btn)

        self._reset_exif_btn = QToolButton()
        self._reset_exif_btn.setIcon(get_icon("reset-exif", "edit-clear", text_fallback="0°"))
        self._reset_exif_btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self._reset_exif_btn.setToolTip(_("Reset EXIF orientation"))
        self._reset_exif_btn.clicked.connect(lambda: self.rotate_requested.emit("reset_exif"))
        self._reset_exif_btn.setEnabled(False)
        tb.addWidget(self._reset_exif_btn)

        sep3 = QToolButton()
        sep3.setEnabled(False)
        sep3.setFixedWidth(8)
        tb.addWidget(sep3)

        for icon_name, fallback, tip, callback in [
            ("open", "▶", _("Open") + "  Ctrl+O", lambda: self.open_requested.emit()),
            ("open-with", "▶…", _("Open with") + "  Ctrl+Shift+O", lambda: self.open_with_requested.emit()),
            ("rename-template", "T", _("Template"), lambda: self.template_requested.emit()),
            ("delete", "✕", _("Delete") + "  Del", lambda: self.delete_requested.emit()),
        ]:
            btn = QToolButton()
            btn.setIcon(get_icon(icon_name, text_fallback=fallback))
            btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
            btn.setToolTip(tip)
            btn.clicked.connect(callback)
            tb.addWidget(btn)

        sep4 = QToolButton()
        sep4.setEnabled(False)
        sep4.setFixedWidth(8)
        tb.addWidget(sep4)

        self._metadata_btn = QToolButton()
        self._metadata_btn.setIcon(get_icon("document-properties", text_fallback="ℹ"))
        self._metadata_btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self._metadata_btn.setToolTip(_("Show metadata panel") + "  I")
        self._metadata_btn.setCheckable(True)
        self._metadata_btn.toggled.connect(self._on_metadata_toggled)
        tb.addWidget(self._metadata_btn)

        tb.addStretch()
        self._zoom_label = QLabel()
        self._zoom_label.setMinimumWidth(180)
        self._zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tb.addWidget(self._zoom_label)

        return tb

    def _setup_shortcuts(self) -> None:
        pairs = [
            (QKeySequence(Qt.Key.Key_0), self._act_fit_window),
            (QKeySequence(Qt.Key.Key_X), self._act_fit_window),
            (QKeySequence(Qt.Key.Key_1), self._act_1to1),
            (QKeySequence(Qt.Key.Key_Z), self._act_1to1),
            (QKeySequence(Qt.Key.Key_W), self._act_fit_width),
            (QKeySequence(Qt.Key.Key_H), self._act_fit_height),
            (QKeySequence(Qt.Key.Key_Plus), self._act_zoom_in),
            (QKeySequence(Qt.Key.Key_Equal), self._act_zoom_in),
            (QKeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_Plus), self._act_zoom_in),
            (QKeySequence(Qt.Key.Key_Minus), self._act_zoom_out),
            (QKeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_Minus), self._act_zoom_out),
            (QKeySequence(Qt.Key.Key_Up), self.navigate_prev),
            (QKeySequence(Qt.Key.Key_Down), self.navigate_next),
            (QKeySequence.StandardKey.Open, self.open_requested),
            (
                QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_O),
                self.open_with_requested,
            ),
            (QKeySequence(Qt.Key.Key_Delete), self.delete_requested),
            (QKeySequence(Qt.Key.Key_Escape), self.close),
            (QKeySequence(Qt.Key.Key_I), self._act_toggle_metadata),
        ]
        for seq, slot in pairs:
            sc = QShortcut(seq, self)
            sc.activated.connect(slot)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_image(self, path: Path) -> None:
        self._current_path = path
        self.setWindowTitle(path.name)
        self._pixmap = load_pixmap(path, auto_rotate=self._auto_rotate)
        if not self._pixmap.isNull():
            w, h = self._pixmap.width(), self._pixmap.height()
            min_dim = min(w, h)
            self._zoom_min = (64 / min_dim) if min_dim >= 64 else 1.0
            self._label.setText("")
        else:
            self._zoom_min = 0.01
            self._label.setText(_("Cannot load image."))
        if self._rotate_auto_btn is not None:
            from pbpicat.image_ops import get_exif_orientation

            has_exif = get_exif_orientation(path) is not None
            self._rotate_auto_btn.setEnabled(has_exif)
            self._reset_exif_btn.setEnabled(has_exif)
        self._apply_zoom(center=True)
        if self._metadata_btn is not None and self._metadata_btn.isChecked():
            self._metadata_panel.load(path, self._sidecar_extensions)

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    def set_metadata_panel_side(self, side: str) -> None:
        if side == self._metadata_side:
            return
        self._metadata_side = side
        self._place_metadata_panel(side)

    def _place_metadata_panel(self, side: str) -> None:
        # QSplitter.insertWidget() moves a widget already in the splitter to the new index.
        first, second = (self._metadata_panel, self._scroll) if side == "left" else (self._scroll, self._metadata_panel)
        self._splitter.insertWidget(0, first)
        self._splitter.insertWidget(1, second)
        self._splitter.setStretchFactor(self._splitter.indexOf(self._scroll), 1)
        self._splitter.setStretchFactor(self._splitter.indexOf(self._metadata_panel), 0)

    def _on_metadata_toggled(self, checked: bool) -> None:
        self._metadata_panel.setVisible(checked)
        if checked:
            if self._splitter.sizes()[self._splitter.indexOf(self._metadata_panel)] == 0:
                total = sum(self._splitter.sizes()) or self.width()
                sizes = [0, 0]
                sizes[self._splitter.indexOf(self._metadata_panel)] = _METADATA_PANEL_DEFAULT_WIDTH
                sizes[self._splitter.indexOf(self._scroll)] = max(1, total - _METADATA_PANEL_DEFAULT_WIDTH)
                self._splitter.setSizes(sizes)
            if self._current_path is not None:
                self._metadata_panel.load(self._current_path, self._sidecar_extensions)
        else:
            self._metadata_panel.clear()
        app_qsettings().setValue("image_viewer/metadata_panel_visible", checked)

    def _act_toggle_metadata(self) -> None:
        self._metadata_btn.toggle()

    def set_auto_rotate(self, value: bool) -> None:
        if self._auto_rotate == value:
            return
        self._auto_rotate = value
        if self._current_path is not None:
            self.load_image(self._current_path)

    def show_message(self, text: str) -> None:
        self._pixmap = QPixmap()
        self._label.setPixmap(QPixmap())
        self._label.setText(text)
        self._zoom_label.setText("")
        self._metadata_panel.clear()

    # ------------------------------------------------------------------
    # Zoom actions
    # ------------------------------------------------------------------

    def _act_1to1(self) -> None:
        self._set_mode(_ZoomMode.ONE_TO_ONE)

    def _act_zoom_in(self) -> None:
        self._apply_custom(self._current_factor() + self._zoom_step)

    def _act_zoom_out(self) -> None:
        self._apply_custom(self._current_factor() - self._zoom_step)

    def _act_fit_width(self) -> None:
        self._set_mode(_ZoomMode.FIT_WIDTH)

    def _act_fit_height(self) -> None:
        self._set_mode(_ZoomMode.FIT_HEIGHT)

    def _act_fit_window(self) -> None:
        self._set_mode(_ZoomMode.FIT_WINDOW)

    # ------------------------------------------------------------------
    # Zoom engine
    # ------------------------------------------------------------------

    def _set_mode(self, mode: _ZoomMode) -> None:
        self._mode = mode
        self._update_button_states()
        self._apply_zoom(center=True)

    def _apply_custom(self, factor: float) -> None:
        self._factor = max(self._zoom_min, min(self._zoom_max, factor))
        self._mode = _ZoomMode.CUSTOM
        self._update_button_states()
        self._apply_zoom()

    def _current_factor(self) -> float:
        """Return the effective zoom factor regardless of mode."""
        if self._pixmap.isNull():
            return 1.0
        vp = self._scroll.viewport()
        w, h = self._pixmap.width(), self._pixmap.height()
        if self._mode == _ZoomMode.FIT_WINDOW:
            if w == 0 or h == 0:
                return 1.0
            fw = vp.width() / w
            fh = vp.height() / h
            return min(fw, fh)
        if self._mode == _ZoomMode.FIT_WIDTH:
            return vp.width() / w if w else 1.0
        if self._mode == _ZoomMode.FIT_HEIGHT:
            return vp.height() / h if h else 1.0
        if self._mode == _ZoomMode.ONE_TO_ONE:
            return 1.0
        return self._factor  # CUSTOM

    def _apply_zoom(self, center: bool = False) -> None:
        if self._pixmap.isNull():
            return

        vp = self._scroll.viewport()
        orig_w, orig_h = self._pixmap.width(), self._pixmap.height()

        if self._mode == _ZoomMode.FIT_WINDOW:
            scaled = self._pixmap.scaled(vp.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        elif self._mode == _ZoomMode.FIT_WIDTH:
            scaled = self._pixmap.scaledToWidth(vp.width(), Qt.SmoothTransformation)
        elif self._mode == _ZoomMode.FIT_HEIGHT:
            scaled = self._pixmap.scaledToHeight(vp.height(), Qt.SmoothTransformation)
        elif self._mode == _ZoomMode.ONE_TO_ONE:
            scaled = self._pixmap
        else:  # CUSTOM
            tw = max(1, int(orig_w * self._factor))
            th = max(1, int(orig_h * self._factor))
            scaled = self._pixmap.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()

        # For CUSTOM (zoom in/out): preserve scroll centre by percentage
        if self._mode == _ZoomMode.CUSTOM:
            hmax_before = hbar.maximum() or 1
            vmax_before = vbar.maximum() or 1
            hpct = hbar.value() / hmax_before
            vpct = vbar.value() / vmax_before

        self._label.setPixmap(scaled)
        self._label.resize(scaled.size())

        if self._mode == _ZoomMode.CUSTOM:
            hbar.setValue(int(hpct * hbar.maximum()))
            vbar.setValue(int(vpct * vbar.maximum()))
        elif center:
            if self._mode == _ZoomMode.ONE_TO_ONE:
                hbar.setValue(hbar.maximum() // 2)
                vbar.setValue(vbar.maximum() // 2)
            elif self._mode == _ZoomMode.FIT_WIDTH:
                vbar.setValue(vbar.maximum() // 2)
            elif self._mode == _ZoomMode.FIT_HEIGHT:
                hbar.setValue(hbar.maximum() // 2)

        # Update zoom label
        factor = scaled.width() / orig_w if orig_w else 1.0
        at_max = self._mode == _ZoomMode.CUSTOM and self._factor >= self._zoom_max
        suffix = _(" (max)") if at_max else ""
        self._zoom_label.setText(f"{orig_w}×{orig_h}  {factor * 100:.0f}%{suffix}")

    def _update_button_states(self) -> None:
        mode_order = [
            _ZoomMode.FIT_WINDOW,
            _ZoomMode.ONE_TO_ONE,
            _ZoomMode.FIT_WIDTH,
            _ZoomMode.FIT_HEIGHT,
        ]
        for btn, mode in zip(self._zoom_buttons, mode_order):
            btn.setChecked(self._mode == mode)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._label:
            etype = event.type()
            if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                if event.modifiers() & Qt.ControlModifier:
                    self._zoom_to_point(event.position().toPoint())
                    return True
                self._drag_pos = event.globalPosition().toPoint()
                self._label.setCursor(Qt.OpenHandCursor)
                return False
            if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.RightButton:
                if event.modifiers() & Qt.ControlModifier:
                    self._zoom_to_point(event.position().toPoint(), direction=-1)
                    return True
            if etype == QEvent.Type.MouseMove and (event.buttons() & Qt.LeftButton) and self._drag_pos is not None:
                pos = event.globalPosition().toPoint()
                delta = pos - self._drag_pos
                self._drag_pos = pos
                self._label.setCursor(Qt.ClosedHandCursor)
                hbar = self._scroll.horizontalScrollBar()
                vbar = self._scroll.verticalScrollBar()
                hbar.setValue(hbar.value() - delta.x())
                vbar.setValue(vbar.value() - delta.y())
                return True
            if etype == QEvent.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._drag_pos = None
                self._label.setCursor(Qt.ArrowCursor)
                return False
            if etype == QEvent.Type.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self._drag_pos = None
                self._center_on_label_pos(event.position().toPoint())
                return True
        return super().eventFilter(obj, event)

    def _center_on_label_pos(self, label_pos) -> None:
        """Scroll to center the viewport on the given label-coordinate point."""
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        vp = self._scroll.viewport()
        hbar.setValue(int(label_pos.x() - vp.width() / 2))
        vbar.setValue(int(label_pos.y() - vp.height() / 2))

    def _zoom_to_point(self, label_pos, direction: int = 1) -> None:
        label_w = self._label.width()
        label_h = self._label.height()
        if label_w == 0 or label_h == 0:
            self._act_zoom_in() if direction > 0 else self._act_zoom_out()
            return
        fx = label_pos.x() / label_w
        fy = label_pos.y() / label_h
        self._factor = max(self._zoom_min, min(self._zoom_max, self._current_factor() + direction * self._zoom_step))
        self._mode = _ZoomMode.CUSTOM
        self._update_button_states()
        self._apply_zoom()
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        vp = self._scroll.viewport()
        hbar.setValue(int(fx * self._label.width() - vp.width() / 2))
        vbar.setValue(int(fy * self._label.height() - vp.height() / 2))

    def closeEvent(self, event) -> None:  # noqa: N802
        app_qsettings().setValue("image_viewer/geometry", self.saveGeometry())
        app_qsettings().setValue("image_viewer/metadata_splitter_state", self._splitter.saveState())
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._mode in (_ZoomMode.FIT_WINDOW, _ZoomMode.FIT_WIDTH, _ZoomMode.FIT_HEIGHT):
            self._apply_zoom()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_zoom(center=True)
