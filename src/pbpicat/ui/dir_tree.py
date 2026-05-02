from pathlib import Path

from PySide6.QtCore import QDir, QTimer, Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class DirTree(QTreeView):
    directory_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_path: str | None = None

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
        self.scrollTo(home_index)
        self.setCurrentIndex(home_index)

        self.selectionModel().currentChanged.connect(self._on_current_changed)

    def current_path(self) -> str:
        idx = self.currentIndex()
        return self._model.filePath(idx) if idx.isValid() else QDir.homePath()

    def select_path(self, path: str) -> None:
        if not Path(path).is_dir():
            return
        self._target_path = path
        self._try_select()

    def _try_select(self) -> None:
        if self._target_path is None:
            return
        idx = self._model.index(self._target_path)
        if not idx.isValid():
            return
        # Expand ancestors top-down so the item becomes visible
        ancestors: list = []
        p = idx.parent()
        while p.isValid():
            ancestors.append(p)
            p = p.parent()
        for anc in reversed(ancestors):
            self.expand(anc)
        self.setCurrentIndex(idx)
        QTimer.singleShot(0, lambda: self.scrollTo(idx))
        self.expand(idx)

    def _on_directory_loaded(self, loaded_path: str) -> None:
        if self._target_path is None:
            return
        # Retry whenever an ancestor directory (or the target itself) finishes loading
        try:
            Path(self._target_path).relative_to(loaded_path)
            self._try_select()
        except ValueError:
            pass

    def _on_current_changed(self, current, _previous):
        if current.isValid():
            self._target_path = None  # Navigation is done
            self.directory_selected.emit(self._model.filePath(current))
