from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pbpicat.config import load_all_history, save_all_history


class _FieldHistoryWidget(QWidget):
    """Editor for the history of a single schema field."""

    def __init__(self, field_key: str, title: str, items: list[str], parent=None):
        super().__init__(parent)
        self._key = field_key
        self._setup_ui(title, items)

    def _setup_ui(self, title: str, items: list[str]) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # List
        list_layout = QVBoxLayout()
        list_layout.addWidget(QLabel(_("History — {title}:").format(title=title)))
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setDragDropMode(QAbstractItemView.InternalMove)
        self._list.setDefaultDropAction(Qt.MoveAction)
        for item in items:
            self._list.addItem(QListWidgetItem(item))
        list_layout.addWidget(self._list)
        root.addLayout(list_layout, stretch=1)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)
        btn_layout.addStretch()

        self._up_btn = QPushButton(_("▲ Move up"))
        self._up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self._up_btn)

        self._down_btn = QPushButton(_("▼ Move down"))
        self._down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self._down_btn)

        btn_layout.addSpacing(12)

        self._del_btn = QPushButton(_("Delete"))
        self._del_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(self._del_btn)

        self._clear_btn = QPushButton(_("Clear all"))
        self._clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self._clear_btn)

        btn_layout.addStretch()
        root.addLayout(btn_layout)

        self._list.currentRowChanged.connect(self._update_buttons)
        self._update_buttons(self._list.currentRow())

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row <= 0:
            return
        item = self._list.takeItem(row)
        self._list.insertItem(row - 1, item)
        self._list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= self._list.count() - 1:
            return
        item = self._list.takeItem(row)
        self._list.insertItem(row + 1, item)
        self._list.setCurrentRow(row + 1)

    def _delete_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _clear_all(self) -> None:
        if self._list.count() == 0:
            return
        reply = QMessageBox.question(
            self,
            _("Clear history"),
            _("Clear all values from this history?"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._list.clear()

    def _update_buttons(self, row: int) -> None:
        has_sel = row >= 0
        self._up_btn.setEnabled(has_sel and row > 0)
        self._down_btn.setEnabled(has_sel and row < self._list.count() - 1)
        self._del_btn.setEnabled(has_sel)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_items(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    @property
    def key(self) -> str:
        return self._key


class HistoryDialog(QDialog):
    """
    Edit the saved history for every schema field.
    Each field gets a tab with a reorderable, deletable list.
    """

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Field histories"))
        self.setMinimumSize(520, 380)
        self._config = config
        self._field_widgets: list[_FieldHistoryWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        count: int = self._config.get("schema_field_count", 6)
        titles: list[str] = self._config.get("schema_field_titles", [])
        history = load_all_history()

        tabs = QTabWidget()
        for i in range(count):
            title = titles[i] if i < len(titles) else _("Field {n}").format(n=i + 1)
            key = f"field_{i}"
            items = history.get(key, [])
            widget = _FieldHistoryWidget(key, title, items)
            self._field_widgets.append(widget)
            tabs.addTab(widget, title)

        filter_title = _("Sidecar filter")
        filter_widget = _FieldHistoryWidget("sidecar_filter", filter_title, history.get("sidecar_filter", []))
        self._field_widgets.append(filter_widget)
        tabs.addTab(filter_widget, filter_title)

        root.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        data = load_all_history()
        for w in self._field_widgets:
            data[w.key] = w.get_items()
        save_all_history(data)
        self.accept()
