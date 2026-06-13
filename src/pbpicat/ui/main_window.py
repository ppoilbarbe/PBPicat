import platform
import re
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pbpicat.config import (
    create_catalog,
    current_catalog,
    delete_catalog,
    duplicate_catalog,
    list_catalogs,
    load_config,
    load_global_config,
    load_history,
    load_last_dest,
    load_last_source_dir,
    qsettings,
    save_history,
    save_last_dest,
    save_last_source_dir,
    set_current_catalog,
)
from pbpicat.renamer import (
    build_rename_plan,
    build_renumber_plan,
    execute_rename,
    execute_renumber,
    undo_rename,
    undo_renumber,
)

from .file_panel import FilePanel
from .history_dialog import HistoryDialog
from .icons import get_icon
from .schema_frame import SchemaFrame
from .settings_dialog import GlobalSettingsDialog, SettingsDialog


class _KeyboardShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Keyboard shortcuts"))
        self.setMinimumSize(520, 440)
        root = QVBoxLayout(self)
        root.setSpacing(8)
        browser = QTextBrowser()
        browser.setReadOnly(True)
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_html())
        root.addWidget(browser)
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignRight)

    @staticmethod
    def _build_html() -> str:
        def row(key: str, desc: str) -> str:
            return f"<tr><td>{key}</td><td>{desc}</td></tr>"

        style = (
            "<style>"
            "body{font-family:sans-serif;margin:0;padding:8px;}"
            "h2{color:#2c5f9e;font-size:12pt;margin:14px 0 4px 0;"
            "border-bottom:1px solid #aac;padding-bottom:3px;}"
            "table{border-collapse:collapse;width:100%;margin-bottom:6px;}"
            "td{padding:4px 10px;vertical-align:top;}"
            "td:first-child{font-family:monospace;font-weight:bold;color:#444;"
            "white-space:nowrap;width:170px;}"
            "tr:nth-child(even){background:#f0f4f8;}"
            "</style>"
        )

        title_main = _("Main window")
        title_viewer = _("Image viewer")

        def key(seq) -> str:
            return QKeySequence(seq).toString(QKeySequence.SequenceFormat.NativeText)

        key_del = key(Qt.Key.Key_Delete)
        key_esc = key(Qt.Key.Key_Escape)
        file_list = _("file list")
        tree_leaf = _("tree leaf")

        main_rows = "".join(
            [
                row("F5", _("Refresh")),
                row(key(QKeySequence.StandardKey.Undo), _("Undo rename")),
                row(key(QKeySequence.StandardKey.Open), _("Open selected file(s)")),
                row(key(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_O), _("Open with…")),
                row(key(Qt.Modifier.CTRL | Qt.Key.Key_N), _("New catalog")),
                row(key(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_D), _("Duplicate catalog")),
                row(key(Qt.Modifier.CTRL | Qt.Key.Key_Comma), _("Open catalog settings")),
                row(key(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_Comma), _("Open program settings")),
                row(key_del, _("Delete selected file(s) and their sidecars")),
                row(f"← / → ({file_list})", _("Move focus to the directory tree")),
                row(f"→ ({tree_leaf})", _("Move focus to the file list")),
            ]
        )

        viewer_rows = "".join(
            [
                row("0", _("Fit window")),
                row("1", _("Actual size (1:1)")),
                row("W", _("Fit width")),
                row("H", _("Fit height")),
                row("+ / −", _("Zoom in / Zoom out")),
                row("↑ / ↓", _("Navigate to previous / next image")),
                row(key_del, _("Delete current image and its sidecars")),
                row(key_esc, _("Close image viewer")),
            ]
        )

        return (
            f"<html><head>{style}</head><body>"
            f"<h2>{title_main}</h2>"
            f"<table>{main_rows}</table>"
            f"<h2>{title_viewer}</h2>"
            f"<table>{viewer_rows}</table>"
            "</body></html>"
        )


class _OrphanSidecarsDialog(QDialog):
    def __init__(self, orphans: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Orphan sidecars"))
        self.setMinimumWidth(420)
        self._orphans: list = list(orphans)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        self._label = QLabel()
        root.addWidget(self._label)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        root.addWidget(self._list)

        btn_layout = QHBoxLayout()

        self._del_sel_btn = QPushButton(_("Delete selected"))
        self._del_sel_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(self._del_sel_btn)

        del_all_btn = QPushButton(_("Delete all"))
        del_all_btn.clicked.connect(self._delete_all)
        btn_layout.addWidget(del_all_btn)

        btn_layout.addStretch()

        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        root.addLayout(btn_layout)
        self._refresh_list()

    def refresh(self, orphans: list) -> None:
        self._orphans = list(orphans)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._label.setText(_("{n} orphan sidecar file(s):").format(n=len(self._orphans)))
        self._list.clear()
        for path in self._orphans:
            self._list.addItem(path.name)
        self._del_sel_btn.setEnabled(bool(self._orphans))

    def _delete_selected(self) -> None:
        rows = sorted({idx.row() for idx in self._list.selectedIndexes()})
        if not rows:
            return
        self._confirm_and_delete([self._orphans[r] for r in rows])

    def _delete_all(self) -> None:
        if not self._orphans:
            return
        self._confirm_and_delete(list(self._orphans))

    def _confirm_and_delete(self, files: list) -> None:
        names = "\n".join(f.name for f in files)
        reply = QMessageBox.question(
            self,
            _("Confirm deletion"),
            _("Permanently delete:\n{names}").format(names=names),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        errors = []
        deleted = set()
        for f in files:
            try:
                f.unlink()
                deleted.add(f)
            except OSError as exc:
                errors.append(f"{f.name}: {exc}")
        self._orphans = [p for p in self._orphans if p not in deleted]
        self._refresh_list()
        if errors:
            QMessageBox.warning(self, _("Deletion error"), "\n".join(errors))
        if not self._orphans:
            self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config = load_config()
        self._undo_stack: list[tuple[str, list]] = []
        self._orphan_dlg: _OrphanSidecarsDialog | None = None
        self._setup_rotation_actions()
        self._setup_ui()
        self._setup_menu()
        self._update_title()
        self.resize(1280, 820)

    def _setup_rotation_actions(self) -> None:
        self._act_rotate_ccw = QAction(_("Rotate 90° CCW"), self)
        self._act_rotate_ccw.setIcon(get_icon("object-rotate-left", text_fallback="↺"))
        self._act_rotate_ccw.setStatusTip(_("Rotate selected image(s) 90° counter-clockwise"))
        self._act_rotate_ccw.setEnabled(False)
        self._act_rotate_ccw.triggered.connect(lambda: self._rotate_selected(-90))

        self._act_rotate_cw = QAction(_("Rotate 90° CW"), self)
        self._act_rotate_cw.setIcon(get_icon("object-rotate-right", text_fallback="↻"))
        self._act_rotate_cw.setStatusTip(_("Rotate selected image(s) 90° clockwise"))
        self._act_rotate_cw.setEnabled(False)
        self._act_rotate_cw.triggered.connect(lambda: self._rotate_selected(90))

        self._act_rotate_180 = QAction(_("Rotate 180°"), self)
        self._act_rotate_180.setIcon(get_icon("object-flip-vertical", text_fallback="↕"))
        self._act_rotate_180.setStatusTip(_("Rotate selected image(s) 180°"))
        self._act_rotate_180.setEnabled(False)
        self._act_rotate_180.triggered.connect(lambda: self._rotate_selected(180))

        self._act_rotate_auto = QAction(_("Apply EXIF orientation"), self)
        self._act_rotate_auto.setIcon(get_icon("media-playlist-repeat", text_fallback="EXIF"))
        self._act_rotate_auto.setStatusTip(_("Apply and remove the EXIF orientation tag"))
        self._act_rotate_auto.setEnabled(False)
        self._act_rotate_auto.triggered.connect(lambda: self._rotate_selected("auto"))

    def _setup_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu(_("&File"))
        act = file_menu.addAction(_("&Quit"), self.close)
        act.setShortcut(QKeySequence.StandardKey.Quit)
        act.setStatusTip(_("Quit the application"))
        act.setIcon(get_icon("application-exit", "application-exit"))

        self._catalog_menu = mb.addMenu(_("&Catalog"))
        act = self._catalog_menu.addAction(_("&New catalog…"), self._new_catalog)
        act.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_N))
        act.setStatusTip(_("Create a new catalog"))
        act.setIcon(get_icon("folder-new", "folder-new"))
        act = self._catalog_menu.addAction(_("&Delete catalog…"), self._delete_catalog_action)
        act.setStatusTip(_("Delete a catalog"))
        act.setIcon(get_icon("delete", "edit-delete"))
        act = self._catalog_menu.addAction(_("D&uplicate catalog…"), self._duplicate_catalog_action)
        act.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_D))
        act.setStatusTip(_("Duplicate the current catalog"))
        act.setIcon(get_icon("edit-copy", "edit-copy"))
        self._catalog_menu.addSeparator()
        self._catalog_menu.aboutToShow.connect(self._populate_catalog_list)

        images_menu = mb.addMenu(_("&Images"))
        self._act_img_open = images_menu.addAction(_("&Open"), self._img_open)
        self._act_img_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_img_open.setStatusTip(_("Open selected file(s) with the default application"))
        self._act_img_open.setIcon(get_icon("open", "document-open"))
        self._act_img_open_with = images_menu.addAction(_("Open &with…"), self._img_open_with)
        self._act_img_open_with.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_O))
        self._act_img_open_with.setStatusTip(_("Open selected file with a chosen application"))
        self._act_img_open_with.setIcon(get_icon("open_with", "document-open"))
        images_menu.addSeparator()
        self._act_img_template = images_menu.addAction(_("&Template"), self._img_template)
        self._act_img_template.setStatusTip(_("Infer rename template from the selected file name"))
        self._act_img_template.setIcon(get_icon("template", "view-list-details"))
        images_menu.addSeparator()
        self._act_img_delete = images_menu.addAction(_("&Delete"), self._img_delete)
        self._act_img_delete.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self._act_img_delete.setStatusTip(_("Permanently delete the selected file(s)"))
        self._act_img_delete.setIcon(get_icon("delete", "edit-delete"))
        for act in (self._act_img_open, self._act_img_open_with, self._act_img_template, self._act_img_delete):
            act.setEnabled(False)
        images_menu.addSeparator()
        images_menu.addAction(self._act_rotate_ccw)
        images_menu.addAction(self._act_rotate_cw)
        images_menu.addAction(self._act_rotate_180)
        images_menu.addAction(self._act_rotate_auto)
        images_menu.addSeparator()
        act = images_menu.addAction(_("&Refresh"), self._refresh)
        act.setShortcut(QKeySequence(Qt.Key.Key_F5))
        act.setStatusTip(_("Refresh"))
        act.setIcon(get_icon("view-refresh", "view-refresh"))

        settings_menu = mb.addMenu(_("&Settings"))
        act = settings_menu.addAction(_("&Catalog configuration…"), self._open_settings)
        act.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Comma))
        act.setStatusTip(_("Open catalog settings"))
        act.setIcon(get_icon("configure", "configure"))
        act = settings_menu.addAction(_("&History…"), self._open_history)
        act.setStatusTip(_("Edit field and filter history"))
        act.setIcon(get_icon("document-open-recent", "document-open-recent"))
        settings_menu.addSeparator()
        act = settings_menu.addAction(_("&Program settings…"), self._open_global_settings)
        act.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_Comma))
        act.setStatusTip(_("Open program settings"))
        act.setIcon(get_icon("preferences-system", "preferences-system"))

        help_menu = mb.addMenu(_("&Help"))
        act = help_menu.addAction(_("&Keyboard shortcuts…"), self._show_keyboard_shortcuts)
        act.setShortcut(QKeySequence(Qt.Key.Key_F1))
        act.setStatusTip(_("Show keyboard shortcuts"))
        act.setIcon(get_icon("help-keyboard-shortcuts", "help-keyboard-shortcuts"))
        help_menu.addSeparator()
        act = help_menu.addAction(_("&About"), self._about)
        act.setStatusTip(_("About PBPicat"))
        act.setIcon(get_icon("help-about", "help-about"))

        self._file_panel.file_list.set_context_actions(
            self._act_img_open,
            self._act_img_open_with,
            self._act_img_template,
            self._act_img_delete,
        )
        self._file_panel.file_list.set_rotation_actions(
            self._act_rotate_ccw,
            self._act_rotate_cw,
            self._act_rotate_180,
            self._act_rotate_auto,
        )

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        root.addLayout(self._build_dest_zone())

        self._schema_frame = SchemaFrame(self._config)
        root.addWidget(self._schema_frame)

        self._file_panel = FilePanel(self._config)
        root.addWidget(self._file_panel, stretch=1)

        root.addLayout(self._build_button_zone())

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage(_("Ready."))

        self._file_panel.file_list.rename_requested.connect(self._rename_files)
        self._file_panel.file_list.schema_proposed.connect(self._apply_proposed_schema)
        self._file_panel.file_list.set_schema_getter(self._schema_frame.get_fields)
        self._file_panel.file_list.set_video_marker_pos_getter(self._schema_frame.get_video_marker_pos)
        self._file_panel.file_list.set_rotate_callback(self._rotate_images)
        self._file_panel.file_list.file_count_changed.connect(self._on_file_count_changed)
        self._file_panel.file_list.itemSelectionChanged.connect(self._update_rename_btn)
        self._file_panel.file_list.itemSelectionChanged.connect(self._update_image_actions)
        self._file_panel.file_list.orphan_sidecar_count_changed.connect(self._on_orphan_count_changed)

        self._file_panel.dir_tree.directory_selected.connect(self._on_directory_changed)
        self._file_panel.dir_tree.select_path(load_last_source_dir())

        geom = qsettings().value("main_window/geometry")
        if geom:
            self.restoreGeometry(geom)

    def _build_dest_zone(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(_("Destination:")))
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText(_("Destination root directory (DEST_ROOTDIR)…"))
        self._dest_edit.setText(load_last_dest())
        layout.addWidget(self._dest_edit, stretch=1)

        browse_btn = QPushButton(_("Browse…"))
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse_dest)
        layout.addWidget(browse_btn)

        self._rename_all_btn = QPushButton(_("Rename all"))
        self._rename_all_btn.setFixedWidth(130)
        self._rename_all_btn.clicked.connect(self._rename_all)
        self._rename_all_btn.setToolTip(_("Rename all files in the current directory according to the schema"))
        self._rename_all_btn.setEnabled(False)
        layout.addWidget(self._rename_all_btn)

        self._renumber_btn = QPushButton(_("Renumber from 1"))
        self._renumber_btn.setFixedWidth(140)
        self._renumber_btn.clicked.connect(self._renumber_all)
        self._renumber_btn.setToolTip(_("Renumber all files in the current directory starting from 1"))
        self._renumber_btn.setEnabled(False)
        layout.addWidget(self._renumber_btn)

        return layout

    def _build_button_zone(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._undo_btn = QPushButton(_("Undo rename"))
        self._undo_btn.setToolTip(_("Undo last operation"))
        self._undo_btn.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_btn.clicked.connect(self._undo_last_rename)
        self._undo_btn.setEnabled(False)
        layout.addWidget(self._undo_btn)

        layout.addStretch()

        self._sort_by_date_chk = QCheckBox(_("Sort by date"))
        self._sort_by_date_chk.setToolTip(_("Sort files by modification date (unchecked: sort by name)"))
        self._sort_by_date_chk.setChecked(False)
        self._sort_by_date_chk.toggled.connect(self._on_sort_by_date_changed)
        layout.addWidget(self._sort_by_date_chk)

        self._sort_reverse_chk = QCheckBox(_("Reverse sort"))
        self._sort_reverse_chk.setToolTip(_("Reverse the sort order"))
        self._sort_reverse_chk.setChecked(False)
        self._sort_reverse_chk.toggled.connect(self._on_sort_reverse_changed)
        layout.addWidget(self._sort_reverse_chk)

        self._filter_edit = QComboBox()
        self._filter_edit.setEditable(True)
        self._filter_edit.setInsertPolicy(QComboBox.NoInsert)
        self._filter_edit.setFixedWidth(260)
        self._filter_edit.lineEdit().setPlaceholderText(_("Sidecar filter…"))
        self._filter_edit.setToolTip(
            _(
                "<b>Sidecar content filter</b><br>"
                "Python regular expression applied to the <i>content</i> of sidecar files.<br>"
                "Only files with at least one sidecar whose content matches are shown.<br>"
                "Files with no sidecar are always hidden when a filter is active.<br>"
                "<tt>.*</tt> matches across line breaks (re.DOTALL).<br>"
                "Case-insensitive (re.IGNORECASE), including accented characters.<br>"
                "Leave empty to show all files."
            )
        )
        for item in load_history("sidecar_filter"):
            self._filter_edit.addItem(item)
        self._filter_edit.setCurrentIndex(-1)
        self._filter_edit.currentTextChanged.connect(self._on_filter_changed)
        self._filter_edit.lineEdit().returnPressed.connect(self._save_filter_to_history)
        layout.addWidget(self._filter_edit)

        self._orphan_btn = QPushButton(_("Orphan sidecars"))
        self._orphan_btn.setToolTip(_("Show orphan sidecar files (no matching image or video)"))
        self._orphan_btn.clicked.connect(self._show_orphan_dialog)
        self._orphan_btn.setEnabled(False)
        layout.addWidget(self._orphan_btn)

        layout.addStretch()

        self._rename_btn = QPushButton(_("Rename selection"))
        self._rename_btn.setToolTip(_("Rename selected files according to the schema"))
        self._rename_btn.clicked.connect(self._rename_selected)
        self._rename_btn.setEnabled(False)
        layout.addWidget(self._rename_btn)

        return layout

    def _on_file_count_changed(self, n: int) -> None:
        self._rename_all_btn.setEnabled(n > 0)
        self._renumber_btn.setEnabled(n > 0)

    def _browse_dest(self) -> None:
        current = self._dest_edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, _("Choose destination directory"), current)
        if path:
            self._dest_edit.setText(path)
            save_last_dest(path)

    def _refresh(self) -> None:
        self._file_panel.refresh()

    def _update_rename_btn(self) -> None:
        self._rename_btn.setEnabled(bool(self._file_panel.file_list.get_selected_files()))

    def _update_image_actions(self) -> None:
        selected = self._file_panel.file_list.get_selected_files()
        n = len(selected)
        any_sel = n > 0
        self._act_img_open.setEnabled(any_sel)
        self._act_img_open_with.setEnabled(any_sel)
        self._act_img_template.setEnabled(n == 1)
        self._act_img_delete.setEnabled(any_sel)

        image_exts = set(self._config.get("image_extensions", []))
        img_sel = [p for p in selected if p.suffix.lower() in image_exts]
        n_img = len(img_sel)
        for act in (self._act_rotate_ccw, self._act_rotate_cw, self._act_rotate_180):
            act.setEnabled(n_img > 0)
        has_exif = any(self._selected_image_has_exif_orientation(p) for p in img_sel)
        self._act_rotate_auto.setEnabled(has_exif)

    def _selected_image_has_exif_orientation(self, path) -> bool:
        from pbpicat.image_ops import get_exif_orientation

        return get_exif_orientation(path) is not None

    def _img_open(self) -> None:
        self._file_panel.file_list.open_selected()

    def _img_open_with(self) -> None:
        self._file_panel.file_list.open_with_selected()

    def _img_template(self) -> None:
        self._file_panel.file_list.template_selected()

    def _img_delete(self) -> None:
        self._file_panel.file_list.delete_selected()

    def _on_sort_by_date_changed(self, checked: bool) -> None:
        self._file_panel.file_list.set_sort_by_date(checked)

    def _on_sort_reverse_changed(self, checked: bool) -> None:
        self._file_panel.file_list.set_sort_reverse(checked)

    def _on_filter_changed(self, text: str) -> None:
        if text:
            try:
                re.compile(text, re.DOTALL | re.IGNORECASE)
                self._filter_edit.lineEdit().setStyleSheet("")
            except re.error:
                self._filter_edit.lineEdit().setStyleSheet("border: 1px solid red;")
                return
        else:
            self._filter_edit.lineEdit().setStyleSheet("")
        self._file_panel.file_list.set_sidecar_filter(text)

    def _on_orphan_count_changed(self, n: int) -> None:
        self._orphan_btn.setEnabled(n > 0)
        if self._orphan_dlg is not None and self._orphan_dlg.isVisible():
            self._orphan_dlg.refresh(self._file_panel.file_list.get_orphan_sidecars())

    def _show_orphan_dialog(self) -> None:
        orphans = self._file_panel.file_list.get_orphan_sidecars()
        self._orphan_dlg = _OrphanSidecarsDialog(orphans, self)
        self._orphan_dlg.exec()
        self._orphan_dlg = None

    def _save_filter_to_history(self) -> None:
        text = self._filter_edit.currentText().strip()
        if not text:
            return
        try:
            re.compile(text, re.DOTALL | re.IGNORECASE)
        except re.error:
            return
        items = [self._filter_edit.itemText(i) for i in range(self._filter_edit.count())]
        if text in items:
            items.remove(text)
        items.insert(0, text)
        items = items[: self._config["history_max"]]
        self._filter_edit.blockSignals(True)
        self._filter_edit.clear()
        for item in items:
            self._filter_edit.addItem(item)
        self._filter_edit.setCurrentText(text)
        self._filter_edit.blockSignals(False)
        save_history("sidecar_filter", items)

    def _reload_filter_history(self) -> None:
        current = self._filter_edit.currentText()
        self._filter_edit.blockSignals(True)
        self._filter_edit.clear()
        for item in load_history("sidecar_filter"):
            self._filter_edit.addItem(item)
        self._filter_edit.setCurrentText(current)
        self._filter_edit.blockSignals(False)

    def _on_directory_changed(self, _path: str) -> None:
        if self._filter_edit.currentText():
            self._filter_edit.clearEditText()

    def _rotate_selected(self, op) -> None:
        selected = self._file_panel.file_list.get_selected_files()
        image_exts = set(self._config.get("image_extensions", []))
        paths = [p for p in selected if p.suffix.lower() in image_exts]
        if op == "auto":
            from pbpicat.image_ops import get_exif_orientation

            paths = [p for p in paths if get_exif_orientation(p) is not None]
        self._rotate_images(paths, op)

    def _rotate_images(self, paths: list, op) -> None:
        from pbpicat.image_ops import get_exif_orientation, rotate_lossless

        if not paths:
            return
        pairs = []
        for path in paths:
            try:
                orig_orient = get_exif_orientation(path)
                undo_op = rotate_lossless(path, op)
                pairs.append((path, undo_op, orig_orient))
            except RuntimeError as exc:
                QMessageBox.warning(self, _("Rotation unavailable"), str(exc))
                break
            except ValueError:
                continue
        if pairs:
            self._undo_stack.append(("rotation", pairs))
            self._update_undo_btn()
            self._status.showMessage(_("{n} file(s) rotated.").format(n=len(pairs)))
            self._file_panel.file_list.refresh_thumbnails_for_paths({p for p, *_ in pairs})

    def _rename_selected(self) -> None:
        files = self._file_panel.file_list.get_selected_files()
        if not files:
            self._status.showMessage(_("No file selected."))
            return
        self._rename_files(files)

    def _rename_all(self) -> None:
        files = self._file_panel.file_list.get_all_files()
        if not files:
            self._status.showMessage(_("No files to rename in the current directory."))
            return
        reply = QMessageBox.question(
            self,
            _("Confirm rename"),
            _("Rename {n} file(s) according to the current schema?").format(n=len(files)),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._rename_files(files)

    def _renumber_all(self) -> None:
        files = self._file_panel.file_list.get_all_files()
        if not files:
            return
        schema_fields = self._schema_frame.get_fields()
        try:
            plan = build_renumber_plan(
                schema_fields,
                [Path(p) for p in files],
                self._config.get("sidecar_extensions", []),
                self._config.get("image_extensions", []),
                self._config.get("video_extensions", []),
                self._config.get("video_marker", ""),
                self._schema_frame.get_video_marker_pos(),
            )
        except ValueError as exc:
            QMessageBox.critical(self, _("Rename error"), str(exc))
            return
        if not plan:
            self._status.showMessage(_("Files are already correctly numbered."))
            return
        reply = QMessageBox.question(
            self,
            _("Confirm renumber"),
            _("Renumber {n} file(s) starting from 1?").format(n=len(files)),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            execute_renumber(plan)
        except RuntimeError as exc:
            QMessageBox.critical(self, _("Rename error"), str(exc))
            self._status.showMessage(_("Error: rename cancelled."))
            return
        self._undo_stack.append(("renumber", plan))
        self._update_undo_btn()
        self._status.showMessage(_("{n} file(s) renumbered successfully.").format(n=len(files)))
        self._file_panel.file_list.refresh_and_select(0)

    def _rename_files(self, file_paths: list) -> None:
        dest_root = self._dest_edit.text().strip()
        if not dest_root:
            QMessageBox.warning(self, _("Missing destination"), _("Please specify a destination directory."))
            return

        schema_fields = self._schema_frame.get_fields()

        try:
            plan = build_rename_plan(
                dest_root,
                schema_fields,
                [Path(p) for p in file_paths],
                self._config.get("sidecar_extensions", []),
                self._config.get("image_extensions", []),
                self._config.get("video_extensions", []),
                self._config.get("video_marker", ""),
                self._schema_frame.get_video_marker_pos(),
            )
            execute_rename(plan)
        except (ValueError, FileExistsError, RuntimeError) as exc:
            QMessageBox.critical(self, _("Rename error"), str(exc))
            self._status.showMessage(_("Error: rename cancelled."))
            return

        self._schema_frame.push_history(schema_fields)
        save_last_dest(dest_root)

        self._undo_stack.append(("rename", plan))
        self._update_undo_btn()

        media_exts = set(self._config.get("image_extensions", [])) | set(self._config.get("video_extensions", []))
        n = len([p for p, _ in plan if p.suffix.lower() in media_exts])
        self._status.showMessage(_("{n} file(s) renamed successfully.").format(n=n))
        next_row = self._file_panel.file_list.next_row_after_files(file_paths)
        self._file_panel.file_list.refresh_and_select(next_row)

    def _update_undo_btn(self) -> None:
        n = len(self._undo_stack)
        if n:
            kind = self._undo_stack[-1][0]
            if kind == "rotation":
                label = _("Undo rotation ({n})").format(n=n)
                tip = _("Undo last rotation (restores original pixel data)")
            else:
                label = _("Undo rename ({n})").format(n=n)
                tip = _("Undo last rename (restores files to their original location)")
            self._undo_btn.setText(label)
            self._undo_btn.setToolTip(tip)
            self._undo_btn.setEnabled(True)
        else:
            self._undo_btn.setText(_("Undo rename"))
            self._undo_btn.setToolTip(_("Undo last rename (restores files to their original location)"))
            self._undo_btn.setEnabled(False)

    def _undo_last_rename(self) -> None:
        if not self._undo_stack:
            return
        kind, plan = self._undo_stack[-1]
        try:
            if kind == "renumber":
                undo_renumber(plan)
            elif kind == "rotation":
                from pbpicat.image_ops import rotate_lossless, set_exif_orientation

                for path, undo_op, orig_orient in plan:
                    rotate_lossless(path, undo_op)
                    if orig_orient is not None:
                        set_exif_orientation(path, orig_orient)
            else:
                undo_rename(plan)
        except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, _("Undo error"), str(exc))
            self._status.showMessage(_("Error: undo failed."))
            return
        self._undo_stack.pop()
        self._update_undo_btn()
        if kind == "rotation":
            self._status.showMessage(_("Rotation undone."))
            self._file_panel.file_list.refresh_thumbnails_for_paths({p for p, *_ in plan})
        else:
            self._status.showMessage(_("Last rename undone."))
            restored = {src for src, _dst in plan}
            self._file_panel.file_list.refresh_and_select_paths(restored)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._config, self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._config = dlg.updated_config()
            self._schema_frame.rebuild(self._config)
            self._file_panel.reconfigure(self._config)
            self._status.showMessage(_("Settings saved."))

    def _open_global_settings(self) -> None:
        dlg = GlobalSettingsDialog(self)
        if dlg.exec() == GlobalSettingsDialog.Accepted:
            self._status.showMessage(_("Program settings saved."))

    def _open_history(self) -> None:
        dlg = HistoryDialog(self._config, self)
        if dlg.exec() == HistoryDialog.Accepted:
            self._schema_frame.rebuild(self._config)
            self._reload_filter_history()
            self._status.showMessage(_("History saved."))

    def _apply_proposed_schema(self, fields: list[str]) -> None:
        self._schema_frame.set_fields(fields)
        self._status.showMessage(_("Template applied from history."))

    # -----------------------------------------------------------------------
    # Catalog management
    # -----------------------------------------------------------------------

    def _update_title(self) -> None:
        cat = current_catalog()
        if cat == "default":
            self.setWindowTitle(_("PBPicat — Image & Video File Renamer"))
        else:
            self.setWindowTitle(_("PBPicat — Image & Video File Renamer [{catalog}]").format(catalog=cat))

    def _populate_catalog_list(self) -> None:
        actions = self._catalog_menu.actions()
        sep_idx = next(i for i, a in enumerate(actions) if a.isSeparator())
        for a in actions[sep_idx + 1 :]:
            self._catalog_menu.removeAction(a)
        active = current_catalog()
        for name in list_catalogs():
            action = self._catalog_menu.addAction(name, lambda n=name: self._switch_to_catalog(n))
            action.setCheckable(True)
            action.setChecked(name == active)
            action.setIcon(get_icon("folder-open", "folder-open"))

    def _new_catalog(self) -> None:
        name, ok = QInputDialog.getText(
            self, _("New catalog"), _("Catalog name (letters, digits, hyphens, underscores):")
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
            QMessageBox.warning(
                self,
                _("Invalid name"),
                _("Catalog name may only contain letters, digits, hyphens, or underscores."),
            )
            return
        if name in list_catalogs():
            QMessageBox.warning(
                self,
                _("Already exists"),
                _('A catalog named "{name}" already exists.').format(name=name),
            )
            return
        global_cfg = load_global_config()
        initial = {"sidecar_extensions": global_cfg["default_sidecar_extensions"]}
        create_catalog(name, initial)
        self._switch_to_catalog(name)

    def _delete_catalog_action(self) -> None:
        candidates = [c for c in list_catalogs() if c != "default"]
        if not candidates:
            QMessageBox.information(
                self,
                _("No catalogs"),
                _('There are no additional catalogs to delete ("default" cannot be deleted).'),
            )
            return
        name, ok = QInputDialog.getItem(self, _("Delete catalog"), _("Select catalog to delete:"), candidates, 0, False)
        if not ok:
            return
        reply = QMessageBox.question(
            self,
            _("Confirm deletion"),
            _('Delete catalog "{name}" and all its settings? This cannot be undone.').format(name=name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        if current_catalog() == name:
            self._switch_to_catalog("default")
        delete_catalog(name)
        self._status.showMessage(_('Catalog "{name}" deleted.').format(name=name))

    def _duplicate_catalog_action(self) -> None:
        source = current_catalog()
        name, ok = QInputDialog.getText(
            self,
            _("Duplicate catalog"),
            _('New catalog name (copy of "{source}"):').format(source=source),
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
            QMessageBox.warning(
                self,
                _("Invalid name"),
                _("Catalog name may only contain letters, digits, hyphens, or underscores."),
            )
            return
        if name in list_catalogs():
            QMessageBox.warning(
                self,
                _("Already exists"),
                _('A catalog named "{name}" already exists.').format(name=name),
            )
            return
        duplicate_catalog(source, name)
        self._status.showMessage(_('Catalog "{source}" duplicated as "{name}".').format(source=source, name=name))

    def _save_current_catalog_state(self) -> None:
        save_last_source_dir(self._file_panel.dir_tree.current_path())
        save_last_dest(self._dest_edit.text().strip())
        qs = qsettings()
        qs.setValue("main_window/geometry", self.saveGeometry())
        qs.sync()

    def _switch_to_catalog(self, name: str) -> None:
        if name == current_catalog():
            return
        self._save_current_catalog_state()
        set_current_catalog(name)
        self._config = load_config()
        self._undo_stack.clear()
        self._update_undo_btn()
        self._schema_frame.rebuild(self._config)
        self._file_panel.reconfigure(self._config)
        self._reload_filter_history()
        self._dest_edit.setText(load_last_dest())
        self._file_panel.dir_tree.select_path(load_last_source_dir())
        self._update_title()
        self._status.showMessage(_('Switched to catalog "{name}".').format(name=name))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_current_catalog_state()
        super().closeEvent(event)

    def _show_keyboard_shortcuts(self) -> None:
        dlg = _KeyboardShortcutsDialog(self)
        dlg.exec()

    def _about(self) -> None:
        from email.utils import getaddresses
        from importlib.metadata import metadata

        import PySide6

        version = QCoreApplication.applicationVersion()
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        pyside_version = PySide6.__version__
        os_info = platform.platform()
        meta = metadata("pbpicat")
        authors_html = ", ".join(
            f'<a href="mailto:{email}">{name}</a>' if email else name
            for name, email in getaddresses([meta["Author-email"] or ""])
        )
        QMessageBox.about(
            self,
            _("About PBPicat"),
            _(
                "<b>PBPicat</b> {version}<br>Image and video file renaming tool using a structured schema."
                "<br><br>Supported formats: images (JPEG, PNG, HEIC, RAW…) and videos (MP4, MOV…),"
                "<br>with associated sidecar files (XMP, DOP, PP3…)."
                "<br><br><b>{authors_label}:</b> {authors}"
                "<br><b>Python:</b> {py_version}"
                "<br><b>PySide6:</b> {pyside_version}"
                "<br><b>{platform_label}:</b> {os_info}"
            ).format(
                version=version,
                authors_label=_("Authors"),
                authors=authors_html,
                py_version=py_version,
                pyside_version=pyside_version,
                platform_label=_("Platform"),
                os_info=os_info,
            ),
        )
