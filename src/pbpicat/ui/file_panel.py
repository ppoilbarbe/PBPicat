from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSplitter

from .dir_tree import DirTree
from .file_list_widget import FileListWidget


class FilePanel(QFrame):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        self.dir_tree = DirTree()
        splitter.addWidget(self.dir_tree)

        self.file_list = FileListWidget(self._config)
        splitter.addWidget(self.file_list)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 840])

        layout.addWidget(splitter)

        self.dir_tree.directory_selected.connect(self.file_list.load_directory)

    def refresh(self) -> None:
        self.file_list.refresh()

    def reconfigure(self, config: dict) -> None:
        self._config = config
        self.file_list.reconfigure(config)
