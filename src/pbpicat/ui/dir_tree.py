from pathlib import Path

from PySide6.QtCore import QDir, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QAbstractItemView, QFileSystemModel, QMenu, QTreeView

from .icons import get_icon


class DirTree(QTreeView):
    directory_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_path: str | None = None
        self._scroll_path: str | None = None
        self._file_list = None

    def set_file_list(self, file_list) -> None:
        self._file_list = file_list

        self._model = QFileSystemModel()
        self._model.setRootPath(QDir.rootPath())
        self._model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
        self._model.directoryLoaded.connect(self._on_directory_loaded)
        self.setModel(self._model)

        for col in range(1, self._model.columnCount()):
            self.hideColumn(col)
        self.setHeaderHidden(True)
        self.setAnimated(True)

        root_index = self._model.index(QDir.rootPath())
        self.setRootIndex(root_index)

        home_index = self._model.index(QDir.homePath())
        self.expand(home_index)
        self.setCurrentIndex(home_index)

        self.selectionModel().currentChanged.connect(self._on_current_changed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def current_path(self) -> str:
        idx = self.currentIndex()
        return self._model.filePath(idx) if idx.isValid() else QDir.homePath()

    def select_path(self, path: str) -> None:
        if not Path(path).is_dir():
            return
        self._target_path = path
        self._scroll_path = path
        self._try_select()

    def _try_select(self) -> None:
        if self._target_path is None:
            return
        idx = self._model.index(self._target_path)
        if not idx.isValid():
            return
        ancestors: list = []
        p = idx.parent()
        while p.isValid():
            ancestors.append(p)
            p = p.parent()
        for anc in reversed(ancestors):
            self.expand(anc)
        self.setCurrentIndex(idx)
        self.expand(idx)
        # _target_path cleared by _on_current_changed; _scroll_path persists

    def _do_scroll(self) -> None:
        path = self._scroll_path
        if path is None:
            return
        if self.isVisible():
            QTimer.singleShot(0, lambda: self._scroll_to_path(path))
        # else: showEvent will call _do_scroll when the widget becomes visible

    def _scroll_to_path(self, path: str) -> None:
        idx = self._model.index(path)
        if idx.isValid():
            self.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._do_scroll()

    def _on_directory_loaded(self, loaded_path: str) -> None:
        if self._target_path is not None:
            try:
                Path(self._target_path).relative_to(loaded_path)
                self._try_select()
            except ValueError:
                pass
        # Re-scroll whenever an ancestor of the target finishes loading —
        # new rows inserted above would otherwise push the target out of view.
        if self._scroll_path is not None:
            try:
                Path(self._scroll_path).relative_to(loaded_path)
                self._do_scroll()
            except ValueError:
                pass

    def _show_context_menu(self, pos) -> None:
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        path = self._model.filePath(idx)
        menu = QMenu(self)
        open_action = menu.addAction(get_icon("open", "document-open"), _("Open"))
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action is open_action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Right:
            idx = self.currentIndex()
            super().keyPressEvent(event)
            # Transfer focus if Qt didn't navigate to a child (leaf, or unscanned dir with no loaded children yet)
            if self.currentIndex() == idx and self._model.rowCount(idx) == 0 and self._file_list is not None:
                self._file_list.setFocus()
            return
        super().keyPressEvent(event)

    def _on_current_changed(self, current, _previous):
        if current.isValid():
            path = self._model.filePath(current)
            self._target_path = None
            if path != self._scroll_path:
                self._scroll_path = None
            self.directory_selected.emit(path)
