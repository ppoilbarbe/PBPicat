import re
from pathlib import Path

from PySide6.QtCore import Qt
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

        main_rows = "".join(
            [
                row("Del", _("Delete selected file(s) and their sidecars")),
            ]
        )

        viewer_rows = "".join(
            [
                row("Ctrl+1", _("Actual size (1:1)")),
                row("Ctrl++ / Ctrl+=", _("Zoom in")),
                row("Ctrl+-", _("Zoom out")),
                row("Ctrl+0", _("Fit window")),
                row("Ctrl+W", _("Fit width")),
                row("Ctrl+H", _("Fit height")),
                row("↑ / ↓", _("Navigate to previous / next image")),
                row("Del", _("Delete current image and its sidecars")),
                row("Escape", _("Close image viewer")),
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
        self._undo_stack: list[tuple[str, list[tuple]]] = []
        self._orphan_dlg: _OrphanSidecarsDialog | None = None
        self._setup_ui()
        self._setup_menu()
        self._update_title()
        self.resize(1280, 820)

    def _setup_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu(_("&File"))
        file_menu.addAction(_("&Quit"), self.close)

        self._catalog_menu = mb.addMenu(_("&Catalog"))
        self._catalog_menu.addAction(_("&New catalog…"), self._new_catalog)
        self._catalog_menu.addAction(_("&Delete catalog…"), self._delete_catalog_action)
        self._catalog_menu.addSeparator()
        self._catalog_menu.aboutToShow.connect(self._populate_catalog_list)

        view_menu = mb.addMenu(_("&View"))
        view_menu.addAction(_("&Refresh"), self._refresh)

        settings_menu = mb.addMenu(_("&Settings"))
        settings_menu.addAction(_("&Configuration…"), self._open_settings)
        settings_menu.addAction(_("&History…"), self._open_history)
        settings_menu.addSeparator()
        settings_menu.addAction(_("&Program settings…"), self._open_global_settings)

        help_menu = mb.addMenu(_("&Help"))
        help_menu.addAction(_("&Keyboard shortcuts…"), self._show_keyboard_shortcuts)
        help_menu.addSeparator()
        help_menu.addAction(_("&About"), self._about)

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
        self._file_panel.file_list.file_count_changed.connect(self._on_file_count_changed)
        self._file_panel.file_list.itemSelectionChanged.connect(self._update_rename_btn)
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

        self._undo_btn = QPushButton(_("Undo last rename"))
        self._undo_btn.setToolTip(_("Undo last rename (restores files to their original location)"))
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
        self._undo_btn.setEnabled(True)
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
        self._undo_btn.setEnabled(True)

        media_exts = set(self._config.get("image_extensions", [])) | set(self._config.get("video_extensions", []))
        n = len([p for p, _ in plan if p.suffix.lower() in media_exts])
        self._status.showMessage(_("{n} file(s) renamed successfully.").format(n=n))
        next_row = self._file_panel.file_list.next_row_after_files(file_paths)
        self._file_panel.file_list.refresh_and_select(next_row)

    def _undo_last_rename(self) -> None:
        if not self._undo_stack:
            return
        kind, plan = self._undo_stack[-1]
        try:
            if kind == "renumber":
                undo_renumber(plan)
            else:
                undo_rename(plan)
        except (FileNotFoundError, FileExistsError, RuntimeError) as exc:
            QMessageBox.critical(self, _("Undo error"), str(exc))
            self._status.showMessage(_("Error: undo failed."))
            return
        self._undo_stack.pop()
        self._undo_btn.setEnabled(bool(self._undo_stack))
        self._status.showMessage(_("Last rename undone."))
        self._file_panel.refresh()

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
        self._undo_btn.setEnabled(False)
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
        QMessageBox.about(
            self,
            _("About PBPicat"),
            _(
                "<b>PBPicat</b><br>Image and video file renaming tool using a structured schema."
                "<br><br>Supported formats: images (JPEG, PNG, HEIC, RAW…) and videos (MP4, MOV…),"
                "<br>with associated sidecar files (XMP, DOP, PP3…)."
            ),
        )
