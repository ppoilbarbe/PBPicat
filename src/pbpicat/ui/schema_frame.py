from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pbpicat.config import load_history, load_video_marker_pos, save_history, save_video_marker_pos


class _ForbiddenCharValidator(QValidator):
    def validate(self, text: str, pos: int):
        if "_" in text or "." in text:
            return (QValidator.Invalid, text, pos)
        return (QValidator.Acceptable, text, pos)


class _SchemaField(QWidget):
    def __init__(self, title: str, field_index: int, history_max: int, parent=None):
        super().__init__(parent)
        self._index = field_index
        self._history_max = history_max

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        validator = _ForbiddenCharValidator(self.combo.lineEdit())
        self.combo.lineEdit().setValidator(validator)
        layout.addWidget(self.combo)

        history = load_history(f"field_{field_index}")
        if history:
            for h in history:
                self.combo.addItem(h)
        else:
            self.combo.addItem("")

    def value(self) -> str:
        return self.combo.currentText().strip()

    def push_history(self, value: str) -> None:
        idx = self.combo.findText(value)
        if idx == 0:
            return
        if idx > 0:
            self.combo.removeItem(idx)
        elif idx == -1 and self.combo.count() >= self._history_max:
            self.combo.removeItem(self.combo.count() - 1)
        self.combo.insertItem(0, value)
        self.combo.setCurrentIndex(0)

        items = [self.combo.itemText(i) for i in range(self.combo.count())]
        save_history(f"field_{self._index}", items)


class SchemaFrame(QFrame):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._config = config
        self._fields: list[_SchemaField] = []
        self._marker_radios: list[QRadioButton] = []
        self._marker_group: QButtonGroup | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        outer.addWidget(QLabel(_("<b>Rename schema</b>")))
        outer.addLayout(QHBoxLayout())
        self._setup_fields()

    def rebuild(self, config: dict) -> None:
        self._config = config
        inner = self.layout().itemAt(1)
        if inner is not None:
            layout = inner.layout()
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
        self._fields.clear()
        self._marker_radios.clear()
        self._setup_fields()

    def _setup_fields(self) -> None:
        row = self.layout().itemAt(1).layout()
        count = self._config.get("schema_field_count", 6)
        titles = self._config.get("schema_field_titles", [_("Field {n}").format(n=i + 1) for i in range(count)])
        history_max = self._config.get("history_max", 20)
        saved_pos = load_video_marker_pos()

        self._marker_group = QButtonGroup(self)
        self._marker_radios.clear()

        tooltip = _("Video marker position")
        for i in range(count + 1):
            radio = QRadioButton()
            radio.setToolTip(tooltip)
            radio.setChecked(i == saved_pos)
            self._marker_group.addButton(radio, i)
            self._marker_radios.append(radio)
            row.addWidget(radio)

            if i < count:
                title = titles[i] if i < len(titles) else _("Field {n}").format(n=i + 1)
                field = _SchemaField(title, i, history_max)
                self._fields.append(field)
                row.addWidget(field)

        self._marker_group.idToggled.connect(self._on_marker_pos_changed)

    def get_fields(self) -> list[str]:
        return [f.value() for f in self._fields]

    def get_video_marker_pos(self) -> int:
        if self._marker_group is None:
            return 0
        cid = self._marker_group.checkedId()
        return cid if cid >= 0 else 0

    def push_history(self, fields: list[str]) -> None:
        for f, v in zip(self._fields, fields):
            f.push_history(v)

    def set_fields(self, values: list[str]) -> None:
        for field, val in zip(self._fields, values):
            field.combo.setCurrentText(val)

    def _on_marker_pos_changed(self, button_id: int, checked: bool) -> None:
        if checked:
            save_video_marker_pos(button_id)
