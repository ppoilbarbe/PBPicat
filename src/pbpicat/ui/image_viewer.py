from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pbpicat.config import DEFAULTS, qsettings
from pbpicat.image_io import load_pixmap


class _ZoomMode(Enum):
    FIT_WINDOW = auto()
    FIT_WIDTH = auto()
    FIT_HEIGHT = auto()
    ONE_TO_ONE = auto()
    CUSTOM = auto()


_ICON_SIZE = 22
_ICON_DIR = Path(__file__).parent.parent / "resources"

# Mapping: logical name → FreeDesktop theme name
_THEME_MAP = {
    "zoom_fit": "zoom-fit-best",
    "zoom_original": "zoom-original",
    "zoom_width": "zoom-fit-width",
    "zoom_height": "zoom-fit-height",
    "zoom_in": "zoom-in",
    "zoom_out": "zoom-out",
}


def _get_icon(name: str, fallback: str) -> QIcon:
    theme_icon = QIcon.fromTheme(_THEME_MAP.get(name, ""))
    if not theme_icon.isNull():
        return theme_icon
    svg_path = _ICON_DIR / f"{name}.svg"
    if svg_path.exists():
        icon = QIcon(str(svg_path))
        if not icon.isNull():
            return icon
    return _text_icon(fallback)


def _text_icon(text: str, size: int = _ICON_SIZE) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    f = p.font()
    f.setPixelSize(max(8, size - 6))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, text)
    p.end()
    return QIcon(pix)


class ImageViewer(QWidget):
    """
    Non-modal independent image viewer with zoom toolbar.

    Zoom modes (toolbar, left to right):
      1:1  |  Zoom in  |  Zoom out  |  Width  |  Height  |  Window (default)
    """

    navigate_prev = Signal()
    navigate_next = Signal()
    delete_requested = Signal()

    def __init__(
        self,
        image_path: Path,
        parent=None,
        zoom_step_percent: int = DEFAULTS["zoom_step_percent"],
        zoom_max_percent: int = DEFAULTS["zoom_max_percent"],
    ):
        super().__init__(parent, Qt.Window)
        self.setMinimumSize(300, 200)

        self._zoom_step = 1.0 + zoom_step_percent / 100.0
        self._zoom_max = zoom_max_percent / 100.0
        self._mode = _ZoomMode.FIT_WINDOW
        self._factor = 1.0  # used only in CUSTOM mode
        self._zoom_min = 0.01
        self._drag_pos: QPoint | None = None

        self._setup_ui()
        self._setup_shortcuts()

        saved_geom = qsettings().value("image_viewer/geometry")
        if saved_geom:
            self.restoreGeometry(saved_geom)

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
        root.addWidget(self._scroll, stretch=1)

    def _build_toolbar(self) -> QHBoxLayout:
        tb = QHBoxLayout()
        tb.setSpacing(2)

        specs = [
            ("zoom_fit", "⊡", _("Fit window  0"), self._act_fit_window),
            ("zoom_original", "1:1", _("Actual size (1:1)  1"), self._act_1to1),
            ("zoom_width", "↔", _("Fit width  W"), self._act_fit_width),
            ("zoom_height", "↕", _("Fit height  H"), self._act_fit_height),
        ]

        self._zoom_buttons: list[QToolButton] = []
        for icon_name, fallback, tip, slot in specs:
            btn = QToolButton()
            btn.setIcon(_get_icon(icon_name, fallback))
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
            ("zoom_in", "＋", _("Zoom in  +"), self._act_zoom_in),
            ("zoom_out", "－", _("Zoom out  −"), self._act_zoom_out),
        ]:
            btn = QToolButton()
            btn.setIcon(_get_icon(icon_name, fallback))
            btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            tb.addWidget(btn)

        tb.addStretch()
        self._zoom_label = QLabel()
        self._zoom_label.setMinimumWidth(180)
        self._zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tb.addWidget(self._zoom_label)

        return tb

    def _setup_shortcuts(self) -> None:
        pairs = [
            (QKeySequence(Qt.Key.Key_0), self._act_fit_window),
            (QKeySequence(Qt.Key.Key_1), self._act_1to1),
            (QKeySequence(Qt.Key.Key_W), self._act_fit_width),
            (QKeySequence(Qt.Key.Key_H), self._act_fit_height),
            (QKeySequence(Qt.Key.Key_Plus), self._act_zoom_in),
            (QKeySequence(Qt.Key.Key_Equal), self._act_zoom_in),
            (QKeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_Plus), self._act_zoom_in),
            (QKeySequence(Qt.Key.Key_Minus), self._act_zoom_out),
            (QKeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_Minus), self._act_zoom_out),
            (QKeySequence(Qt.Key.Key_Up), self.navigate_prev),
            (QKeySequence(Qt.Key.Key_Down), self.navigate_next),
            (QKeySequence(Qt.Key.Key_Delete), self.delete_requested),
            (QKeySequence(Qt.Key.Key_Escape), self.close),
        ]
        for seq, slot in pairs:
            sc = QShortcut(seq, self)
            sc.activated.connect(slot)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_image(self, path: Path) -> None:
        self.setWindowTitle(path.name)
        self._pixmap = load_pixmap(path)
        if not self._pixmap.isNull():
            w, h = self._pixmap.width(), self._pixmap.height()
            min_dim = min(w, h)
            self._zoom_min = (64 / min_dim) if min_dim >= 64 else 1.0
            self._label.setText("")
        else:
            self._zoom_min = 0.01
            self._label.setText(_("Cannot load image."))
        self._apply_zoom()

    def show_message(self, text: str) -> None:
        self._pixmap = QPixmap()
        self._label.setPixmap(QPixmap())
        self._label.setText(text)
        self._zoom_label.setText("")

    # ------------------------------------------------------------------
    # Zoom actions
    # ------------------------------------------------------------------

    def _act_1to1(self) -> None:
        self._set_mode(_ZoomMode.ONE_TO_ONE)

    def _act_zoom_in(self) -> None:
        self._apply_custom(self._current_factor() * self._zoom_step)

    def _act_zoom_out(self) -> None:
        self._apply_custom(self._current_factor() / self._zoom_step)

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
        self._apply_zoom()

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

    def _apply_zoom(self) -> None:
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

        # Preserve scroll centre across zoom changes
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        hmax_before = hbar.maximum() or 1
        vmax_before = vbar.maximum() or 1
        hpct = hbar.value() / hmax_before
        vpct = vbar.value() / vmax_before

        self._label.setPixmap(scaled)
        self._label.resize(scaled.size())

        # Restore scroll position
        hbar.setValue(int(hpct * hbar.maximum()))
        vbar.setValue(int(vpct * vbar.maximum()))

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
                self._drag_pos = event.globalPosition().toPoint()
                self._label.setCursor(Qt.OpenHandCursor)
                return False
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
                self._zoom_to_point(event.pos())
                return True
        return super().eventFilter(obj, event)

    def _zoom_to_point(self, label_pos) -> None:
        label_w = self._label.width()
        label_h = self._label.height()
        if label_w == 0 or label_h == 0:
            self._act_zoom_in()
            return
        fx = label_pos.x() / label_w
        fy = label_pos.y() / label_h
        self._factor = max(self._zoom_min, min(self._zoom_max, self._current_factor() * self._zoom_step))
        self._mode = _ZoomMode.CUSTOM
        self._update_button_states()
        self._apply_zoom()
        hbar = self._scroll.horizontalScrollBar()
        vbar = self._scroll.verticalScrollBar()
        vp = self._scroll.viewport()
        hbar.setValue(int(fx * self._label.width() - vp.width() / 2))
        vbar.setValue(int(fy * self._label.height() - vp.height() / 2))

    def closeEvent(self, event) -> None:  # noqa: N802
        qsettings().setValue("image_viewer/geometry", self.saveGeometry())
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._mode in (_ZoomMode.FIT_WINDOW, _ZoomMode.FIT_WIDTH, _ZoomMode.FIT_HEIGHT):
            self._apply_zoom()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_zoom()
