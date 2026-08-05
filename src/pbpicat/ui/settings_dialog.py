import re

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pbpicat.config import (
    DEFAULT_IMAGE_EXTENSIONS,
    DEFAULT_SIDECAR_EXTENSIONS,
    DEFAULT_VIDEO_EXTENSIONS,
    DEFAULTS,
    app_qsettings,
    load_global_config,
    save_config,
    save_global_config,
)

_EXT_RE = re.compile(r"^(\.[a-zA-Z0-9]+)+$")


class _SchemaTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._title_edits: list[QLineEdit] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel(_("Number of fields:")))
        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, 12)
        self._count_spin.setValue(self._config.get("schema_field_count", 6))
        self._count_spin.setFixedWidth(60)
        count_row.addWidget(self._count_spin)
        count_row.addStretch()
        root.addLayout(count_row)

        history_row = QHBoxLayout()
        history_row.addWidget(QLabel(_("Max history entries:")))
        self._history_spin = QSpinBox()
        self._history_spin.setRange(1, 200)
        self._history_spin.setValue(self._config.get("history_max", DEFAULTS["history_max"]))
        self._history_spin.setToolTip(_("Maximum number of values kept per field history and sidecar filter history"))
        self._history_spin.setFixedWidth(60)
        history_row.addWidget(self._history_spin)
        history_row.addStretch()
        root.addLayout(history_row)

        del_list_row = QHBoxLayout()
        del_list_row.addWidget(QLabel(_("Max files listed in deletion confirmation:")))
        self._del_list_spin = QSpinBox()
        self._del_list_spin.setRange(1, 999)
        self._del_list_spin.setValue(self._config.get("delete_list_max_files", DEFAULTS["delete_list_max_files"]))
        self._del_list_spin.setToolTip(
            _("When deleting more files than this threshold, show the count instead of listing each file name")
        )
        self._del_list_spin.setFixedWidth(60)
        del_list_row.addWidget(self._del_list_spin)
        del_list_row.addStretch()
        root.addLayout(del_list_row)

        root.addWidget(QLabel(_("<b>Field titles:</b>")))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.StyledPanel)

        self._titles_container = QWidget()
        self._titles_layout = QFormLayout(self._titles_container)
        self._titles_layout.setSpacing(6)
        scroll.setWidget(self._titles_container)
        root.addWidget(scroll, stretch=1)

        self._rebuild_rows(self._count_spin.value())
        self._count_spin.valueChanged.connect(self._rebuild_rows)

    def _rebuild_rows(self, count: int) -> None:
        current = [e.text() for e in self._title_edits]
        saved: list[str] = self._config.get("schema_field_titles", [])

        while self._titles_layout.rowCount():
            self._titles_layout.removeRow(0)
        self._title_edits.clear()

        for i in range(count):
            text = current[i] if i < len(current) else (saved[i] if i < len(saved) else _("Field {n}").format(n=i + 1))
            edit = QLineEdit(text)
            edit.setPlaceholderText(_("Field {n}").format(n=i + 1))
            self._titles_layout.addRow(_("Field {n}:").format(n=i + 1), edit)
            self._title_edits.append(edit)

    def apply_to(self, config: dict) -> None:
        count = self._count_spin.value()
        titles = [e.text().strip() or _("Field {n}").format(n=i + 1) for i, e in enumerate(self._title_edits)]
        config["schema_field_count"] = count
        config["schema_field_titles"] = titles
        config["history_max"] = self._history_spin.value()
        config["delete_list_max_files"] = self._del_list_spin.value()


class _SidecarTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.addWidget(QLabel(_("Sidecar file extensions (e.g. .xmp, .prompt.txt):")))

        self._list = QListWidget()
        for ext in self._config.get("sidecar_extensions", []):
            self._list.addItem(ext)
        root.addWidget(self._list, stretch=1)

        add_row = QHBoxLayout()
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText(_(".ext or .name.ext"))
        self._ext_edit.setMaximumWidth(120)
        self._ext_edit.returnPressed.connect(self._add_ext)
        add_row.addWidget(self._ext_edit)

        add_btn = QPushButton(_("Add"))
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_ext)
        add_row.addWidget(add_btn)
        add_row.addStretch()

        del_btn = QPushButton(_("Delete"))
        del_btn.setFixedWidth(90)
        del_btn.clicked.connect(self._del_ext)
        add_row.addWidget(del_btn)

        root.addLayout(add_row)

        restore_btn = QPushButton(_("Restore missing defaults"))
        restore_btn.setToolTip(_("Add extensions from the global default list that are not yet in the list above"))
        restore_btn.clicked.connect(self._restore_missing_defaults)
        root.addWidget(restore_btn)

        self._delete_empty_cb = QCheckBox(_("Delete empty sidecar files when loading a directory"))
        self._delete_empty_cb.setToolTip(
            _("Automatically delete zero-byte sidecar files (including orphans) when entering a directory")
        )
        self._delete_empty_cb.setChecked(self._config.get("delete_empty_sidecars", True))
        root.addWidget(self._delete_empty_cb)

        form = QFormLayout()
        form.setSpacing(8)
        self._new_ext_combo = QComboBox()
        self._new_ext_combo.setToolTip(
            _("Extension used when creating a new sidecar by double-clicking the sidecar column")
        )
        form.addRow(_("Default extension for new sidecar:"), self._new_ext_combo)
        root.addLayout(form)

        self._rebuild_new_ext_combo()

    def _rebuild_new_ext_combo(self) -> None:
        current = self._new_ext_combo.currentText()
        self._new_ext_combo.clear()
        for i in range(self._list.count()):
            self._new_ext_combo.addItem(self._list.item(i).text())
        saved = self._config.get("sidecar_new_extension", "")
        target = current or saved
        idx = self._new_ext_combo.findText(target)
        if idx >= 0:
            self._new_ext_combo.setCurrentIndex(idx)

    def _add_ext(self) -> None:
        raw = self._ext_edit.text().strip().lower()
        if not raw.startswith("."):
            raw = "." + raw
        if not _EXT_RE.match(raw):
            QMessageBox.warning(
                self,
                _("Invalid extension"),
                _("'{ext}' is not a valid extension (e.g. .xmp, .prompt.txt).").format(ext=raw),
            )
            return
        if self._list.findItems(raw, Qt.MatchExactly):
            self._ext_edit.clear()
            return
        self._list.addItem(raw)
        self._ext_edit.clear()
        self._rebuild_new_ext_combo()

    def _del_ext(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self._rebuild_new_ext_combo()

    def _restore_missing_defaults(self) -> None:
        defaults = load_global_config()["default_sidecar_extensions"]
        current = {self._list.item(i).text() for i in range(self._list.count())}
        added = 0
        for ext in defaults:
            if ext not in current:
                self._list.addItem(ext)
                added += 1
        if added:
            self._rebuild_new_ext_combo()
        else:
            QMessageBox.information(self, _("Restore defaults"), _("All default extensions are already in the list."))

    def apply_to(self, config: dict) -> None:
        config["sidecar_extensions"] = [self._list.item(i).text() for i in range(self._list.count())]
        config["sidecar_new_extension"] = self._new_ext_combo.currentText()
        config["delete_empty_sidecars"] = self._delete_empty_cb.isChecked()


class _ThumbnailTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addWidget(
            QLabel(
                _(
                    "Maximum size of thumbnails displayed in the file list."
                    "\nA navigation restart is required for the change to take effect."
                )
            )
        )

        form = QFormLayout()
        form.setSpacing(8)

        legacy = self._config.get("thumbnail_size", 128)

        self._w_spin = QSpinBox()
        self._w_spin.setRange(32, 512)
        self._w_spin.setSuffix(" px")
        self._w_spin.setValue(self._config.get("thumbnail_max_width", legacy))
        form.addRow(_("Max width:"), self._w_spin)

        self._h_spin = QSpinBox()
        self._h_spin.setRange(32, 512)
        self._h_spin.setSuffix(" px")
        self._h_spin.setValue(self._config.get("thumbnail_max_height", legacy))
        form.addRow(_("Max height:"), self._h_spin)

        root.addLayout(form)
        root.addStretch()

    def apply_to(self, config: dict) -> None:
        config["thumbnail_max_width"] = self._w_spin.value()
        config["thumbnail_max_height"] = self._h_spin.value()


class _ImageTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.addWidget(QLabel(_("Recognised image extensions (thumbnail + rename):")))

        self._list = QListWidget()
        for ext in self._config.get("image_extensions", []):
            self._list.addItem(ext)
        root.addWidget(self._list, stretch=1)

        add_row = QHBoxLayout()
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText(".ext")
        self._ext_edit.setMaximumWidth(120)
        self._ext_edit.returnPressed.connect(self._add_ext)
        add_row.addWidget(self._ext_edit)

        add_btn = QPushButton(_("Add"))
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_ext)
        add_row.addWidget(add_btn)
        add_row.addStretch()

        del_btn = QPushButton(_("Delete"))
        del_btn.setFixedWidth(90)
        del_btn.clicked.connect(self._del_ext)
        add_row.addWidget(del_btn)

        root.addLayout(add_row)

        restore_btn = QPushButton(_("Restore missing defaults"))
        restore_btn.setToolTip(_("Add extensions from the built-in default list that are not yet in the list above"))
        restore_btn.clicked.connect(self._restore_missing_defaults)
        root.addWidget(restore_btn)

        form = QFormLayout()
        form.setSpacing(8)

        self._step_spin = QSpinBox()
        self._step_spin.setRange(1, 200)
        self._step_spin.setSuffix(" %")
        self._step_spin.setToolTip(_("Enlargement/reduction factor per click or double-click"))
        self._step_spin.setValue(self._config.get("zoom_step_percent", DEFAULTS["zoom_step_percent"]))
        form.addRow(_("Zoom step:"), self._step_spin)

        self._max_spin = QSpinBox()
        self._max_spin.setRange(100, 25600)
        self._max_spin.setSingleStep(100)
        self._max_spin.setSuffix(" %")
        self._max_spin.setToolTip(_("Maximum zoom allowed in the image viewer"))
        self._max_spin.setValue(self._config.get("zoom_max_percent", DEFAULTS["zoom_max_percent"]))
        form.addRow(_("Max zoom:"), self._max_spin)

        self._metadata_side_combo = QComboBox()
        self._metadata_side_combo.addItem(_("Left"), "left")
        self._metadata_side_combo.addItem(_("Right"), "right")
        self._metadata_side_combo.setToolTip(_("Side of the image viewer where the metadata panel opens"))
        idx = self._metadata_side_combo.findData(
            self._config.get("metadata_panel_side", DEFAULTS["metadata_panel_side"])
        )
        if idx >= 0:
            self._metadata_side_combo.setCurrentIndex(idx)
        form.addRow(_("Metadata panel side:"), self._metadata_side_combo)

        root.addLayout(form)

        self._confirm_deletions_cb = QCheckBox(_("Confirm deletions"))
        self._confirm_deletions_cb.setToolTip(_("Ask for confirmation before permanently deleting files"))
        self._confirm_deletions_cb.setChecked(self._config.get("confirm_deletions", True))
        root.addWidget(self._confirm_deletions_cb)

        self._exif_auto_rotate_cb = QCheckBox(_("Apply EXIF rotation"))
        self._exif_auto_rotate_cb.setToolTip(
            _("Automatically rotate thumbnails and viewer according to the image EXIF orientation tag")
        )
        self._exif_auto_rotate_cb.setChecked(self._config.get("exif_auto_rotate", True))
        root.addWidget(self._exif_auto_rotate_cb)

    def _add_ext(self) -> None:
        raw = self._ext_edit.text().strip().lower()
        if not raw.startswith("."):
            raw = "." + raw
        if not _EXT_RE.match(raw):
            QMessageBox.warning(
                self,
                _("Invalid extension"),
                _("'{ext}' is not a valid extension (e.g. .png, .heic).").format(ext=raw),
            )
            return
        if self._list.findItems(raw, Qt.MatchExactly):
            self._ext_edit.clear()
            return
        self._list.addItem(raw)
        self._ext_edit.clear()

    def _del_ext(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _restore_missing_defaults(self) -> None:
        current = {self._list.item(i).text() for i in range(self._list.count())}
        added = 0
        for ext in DEFAULT_IMAGE_EXTENSIONS:
            if ext not in current:
                self._list.addItem(ext)
                added += 1
        if added == 0:
            QMessageBox.information(self, _("Restore defaults"), _("All default extensions are already in the list."))

    def apply_to(self, config: dict) -> None:
        config["image_extensions"] = [self._list.item(i).text() for i in range(self._list.count())]
        config["zoom_step_percent"] = self._step_spin.value()
        config["zoom_max_percent"] = self._max_spin.value()
        config["confirm_deletions"] = self._confirm_deletions_cb.isChecked()
        config["exif_auto_rotate"] = self._exif_auto_rotate_cb.isChecked()
        config["metadata_panel_side"] = self._metadata_side_combo.currentData()


class _BehaviourTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        self._use_trash_cb = QCheckBox(_("Move deleted files to trash"))
        self._use_trash_cb.setToolTip(_("Send files to the system trash instead of deleting them permanently"))
        self._use_trash_cb.setChecked(self._config.get("use_trash", True))
        root.addWidget(self._use_trash_cb)

        root.addStretch()

    def apply_to(self, config: dict) -> None:
        config["use_trash"] = self._use_trash_cb.isChecked()


class _VideoTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        root.addWidget(QLabel(_("Recognised video extensions:")))

        self._list = QListWidget()
        for ext in self._config.get("video_extensions", []):
            self._list.addItem(ext)
        root.addWidget(self._list, stretch=1)

        add_row = QHBoxLayout()
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText(".ext")
        self._ext_edit.setMaximumWidth(120)
        self._ext_edit.returnPressed.connect(self._add_ext)
        add_row.addWidget(self._ext_edit)

        add_btn = QPushButton(_("Add"))
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_ext)
        add_row.addWidget(add_btn)
        add_row.addStretch()

        del_btn = QPushButton(_("Delete"))
        del_btn.setFixedWidth(90)
        del_btn.clicked.connect(self._del_ext)
        add_row.addWidget(del_btn)
        root.addLayout(add_row)

        restore_btn = QPushButton(_("Restore missing defaults"))
        restore_btn.setToolTip(_("Add extensions from the built-in default list that are not yet in the list above"))
        restore_btn.clicked.connect(self._restore_missing_defaults)
        root.addWidget(restore_btn)

        root.addWidget(
            QLabel(
                _(
                    "<b>Video marker</b><br>Inserted among the name components at the position chosen in the schema."
                    "<br>No '_' in the value. Empty = no marker."
                )
            )
        )

        validator = QRegularExpressionValidator(QRegularExpression(r"[^_.]*"))

        form = QFormLayout()
        form.setSpacing(8)

        self._marker_edit = QLineEdit(self._config.get("video_marker", ""))
        self._marker_edit.setPlaceholderText(_("e.g. VID  (empty = none)"))
        self._marker_edit.setValidator(validator)
        form.addRow(_("Marker:"), self._marker_edit)

        root.addLayout(form)

    def _add_ext(self) -> None:
        raw = self._ext_edit.text().strip().lower()
        if not raw.startswith("."):
            raw = "." + raw
        if not _EXT_RE.match(raw):
            QMessageBox.warning(
                self,
                _("Invalid extension"),
                _("'{ext}' is not a valid extension (e.g. .mp4).").format(ext=raw),
            )
            return
        if self._list.findItems(raw, Qt.MatchExactly):
            self._ext_edit.clear()
            return
        self._list.addItem(raw)
        self._ext_edit.clear()

    def _del_ext(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _restore_missing_defaults(self) -> None:
        current = {self._list.item(i).text() for i in range(self._list.count())}
        added = 0
        for ext in DEFAULT_VIDEO_EXTENSIONS:
            if ext not in current:
                self._list.addItem(ext)
                added += 1
        if added == 0:
            QMessageBox.information(self, _("Restore defaults"), _("All default extensions are already in the list."))

    def apply_to(self, config: dict) -> None:
        config["video_extensions"] = [self._list.item(i).text() for i in range(self._list.count())]
        config["video_marker"] = self._marker_edit.text().strip()


class _LanguageTab(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        from pbpicat.i18n import available_languages

        root = QVBoxLayout(self)
        root.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem(_("System default"), "")
        for code, name in available_languages():
            self._lang_combo.addItem(name, code)

        current = self._config.get("language", "")
        idx = self._lang_combo.findData(current)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        form.addRow(_("Interface language:"), self._lang_combo)
        root.addLayout(form)

        root.addWidget(QLabel(_("A restart is required for the language change to take effect.")))
        root.addStretch()

    def apply_to(self, config: dict) -> None:
        config["language"] = self._lang_combo.currentData()


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Configuration"))
        self.setMinimumSize(460, 420)
        self._config = dict(config)
        self._setup_ui()
        geom = app_qsettings().value("settings_dialog/geometry")
        if geom:
            self.restoreGeometry(geom)

    def done(self, result) -> None:  # noqa: N802
        app_qsettings().setValue("settings_dialog/geometry", self.saveGeometry())
        super().done(result)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        self._schema_tab = _SchemaTab(self._config)
        self._sidecar_tab = _SidecarTab(self._config)
        self._image_tab = _ImageTab(self._config)
        self._thumb_tab = _ThumbnailTab(self._config)
        self._video_tab = _VideoTab(self._config)
        self._behaviour_tab = _BehaviourTab(self._config)

        tabs.addTab(self._schema_tab, _("Rename schema"))
        tabs.addTab(self._sidecar_tab, _("Sidecar extensions"))
        tabs.addTab(self._image_tab, _("Images"))
        tabs.addTab(self._video_tab, _("Video"))
        tabs.addTab(self._thumb_tab, _("Thumbnails"))
        tabs.addTab(self._behaviour_tab, _("Behaviour"))

        root.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        self._schema_tab.apply_to(self._config)
        self._sidecar_tab.apply_to(self._config)
        self._image_tab.apply_to(self._config)
        self._video_tab.apply_to(self._config)
        self._thumb_tab.apply_to(self._config)
        self._behaviour_tab.apply_to(self._config)
        save_config(self._config)
        self.accept()

    def updated_config(self) -> dict:
        return self._config


class GlobalSettingsDialog(QDialog):
    """Program-level settings (not per-catalog)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Program settings"))
        self.setMinimumSize(460, 380)
        self._global_config = load_global_config()
        self._setup_ui()
        geom = app_qsettings().value("global_settings_dialog/geometry")
        if geom:
            self.restoreGeometry(geom)

    def done(self, result) -> None:  # noqa: N802
        app_qsettings().setValue("global_settings_dialog/geometry", self.saveGeometry())
        super().done(result)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_sidecar_tab(), _("Sidecar extensions"))
        tabs.addTab(self._build_language_tab(), _("Language"))
        root.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_sidecar_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        layout.addWidget(QLabel(_("<b>Default sidecar extensions for new catalogs</b>")))
        layout.addWidget(QLabel(_("(e.g. .xmp, .dop, .prompt.txt)")))

        self._list = QListWidget()
        for ext in self._global_config.get("default_sidecar_extensions", []):
            self._list.addItem(ext)
        layout.addWidget(self._list, stretch=1)

        add_row = QHBoxLayout()
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText(_(".ext or .name.ext"))
        self._ext_edit.setMaximumWidth(140)
        self._ext_edit.returnPressed.connect(self._add_ext)
        add_row.addWidget(self._ext_edit)

        add_btn = QPushButton(_("Add"))
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_ext)
        add_row.addWidget(add_btn)
        add_row.addStretch()

        del_btn = QPushButton(_("Delete"))
        del_btn.setFixedWidth(90)
        del_btn.clicked.connect(self._del_ext)
        add_row.addWidget(del_btn)
        layout.addLayout(add_row)

        restore_btn = QPushButton(_("Restore built-in defaults"))
        restore_btn.setToolTip(_("Reset the list to the built-in default sidecar extensions"))
        restore_btn.clicked.connect(self._restore_defaults)
        layout.addWidget(restore_btn)

        return w

    def _build_language_tab(self) -> QWidget:
        from pbpicat.i18n import available_languages

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem(_("System default"), "")
        for code, name in available_languages():
            self._lang_combo.addItem(name, code)

        current = self._global_config.get("language", "")
        idx = self._lang_combo.findData(current)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        form.addRow(_("Interface language:"), self._lang_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel(_("A restart is required for the language change to take effect.")))
        layout.addStretch()

        return w

    def _add_ext(self) -> None:
        raw = self._ext_edit.text().strip().lower()
        if not raw.startswith("."):
            raw = "." + raw
        if not _EXT_RE.match(raw):
            QMessageBox.warning(
                self,
                _("Invalid extension"),
                _("'{ext}' is not a valid extension (e.g. .xmp, .prompt.txt).").format(ext=raw),
            )
            return
        if self._list.findItems(raw, Qt.MatchExactly):
            self._ext_edit.clear()
            return
        self._list.addItem(raw)
        self._ext_edit.clear()

    def _del_ext(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _restore_defaults(self) -> None:
        self._list.clear()
        for ext in DEFAULT_SIDECAR_EXTENSIONS:
            self._list.addItem(ext)

    def _accept(self) -> None:
        self._global_config["default_sidecar_extensions"] = [
            self._list.item(i).text() for i in range(self._list.count())
        ]
        self._global_config["language"] = self._lang_combo.currentData()
        save_global_config(self._global_config)
        self.accept()

    def updated_global_config(self) -> dict:
        return self._global_config
