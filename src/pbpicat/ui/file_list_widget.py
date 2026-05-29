import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QFileSystemWatcher, QMimeData, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDrag, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
)

from pbpicat.config import load_all_history
from pbpicat.image_io import load_qimage
from pbpicat.renamer import validate_schema

from .image_viewer import ImageViewer


def _natural_sort_key(path: Path) -> str:
    name = re.sub(r"\d+", lambda m: m.group().zfill(7), path.stem)
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return name.lower()


class _SchemaProposalDialog(QDialog):
    """Read-only preview of the inferred schema; user confirms or cancels."""

    def __init__(self, titles: list[str], proposed: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Proposed template"))
        self.setMinimumWidth(360)
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addWidget(QLabel(_("Detected template — confirm to apply to fields:")))

        form = QFormLayout()
        form.setSpacing(6)
        for title, value in zip(titles, proposed):
            if value:
                lbl = QLabel(f"<b>{value}</b>")
            else:
                lbl = QLabel(f"<i style='color:gray'>{_('(empty)')}</i>")
            form.addRow(f"{title} :", lbl)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)


class _ThumbnailWorker(QThread):
    """Load thumbnails in a background thread using QImageReader (thread-safe)."""

    thumbnail_ready = Signal(int, QImage)

    def __init__(self, files: list[Path], thumb_w: int, thumb_h: int, image_exts: set[str], parent=None):
        super().__init__(parent)
        self._files = files
        self._w = thumb_w
        self._h = thumb_h
        self._image_exts = image_exts
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for i, path in enumerate(self._files):
            if self._cancelled:
                break
            if path.suffix.lower() not in self._image_exts:
                continue
            image = load_qimage(path, self._w, self._h)
            self.thumbnail_ready.emit(i, image)


class FileListWidget(QTableWidget):
    """
    Table displaying image and video files with thumbnail, name and sidecar indicator.

    Columns: THUMB | NAME | SIDECAR

    Signals:
        rename_requested(list[Path])
    """

    rename_requested = Signal(list)
    schema_proposed = Signal(list)
    file_count_changed = Signal(int)
    orphan_sidecar_count_changed = Signal(int)

    _THUMB_COL = 0
    _NAME_COL = 1
    _SIDECAR_COL = 2

    def __init__(self, config: dict, parent=None):
        super().__init__(0, 3, parent)
        self._current_dir: Path | None = None
        self._file_data: list[tuple[Path, list[Path]]] = []
        self._display_data: list[tuple[Path, list[Path]]] = []
        self._orphan_sidecars: list[Path] = []
        self._sidecar_filter: str = ""
        self._sort_by_date: bool = False
        self._sort_reverse: bool = False
        self._worker: _ThumbnailWorker | None = None
        self._image_viewer: ImageViewer | None = None
        self._get_schema_fields: Callable[[], list[str]] | None = None
        self._get_video_marker_pos: Callable[[], int] | None = None
        self._rebuilding: bool = False
        self._sidecars_pending_edit: set[Path] = set()
        self._apply_config(config)
        self._setup_table()
        self.cellDoubleClicked.connect(self._on_double_click)
        self.itemSelectionChanged.connect(self._on_selection_changed)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_dir_changed_on_disk)
        self._refresh_debounce = QTimer(self)
        self._refresh_debounce.setSingleShot(True)
        self._refresh_debounce.setInterval(400)
        self._refresh_debounce.timeout.connect(self.refresh)

    def set_schema_getter(self, getter: Callable[[], list[str]]) -> None:
        self._get_schema_fields = getter

    def set_video_marker_pos_getter(self, getter: Callable[[], int]) -> None:
        self._get_video_marker_pos = getter

    def _apply_config(self, config: dict) -> None:
        legacy = config.get("thumbnail_size", 128)
        self._thumb_w: int = config.get("thumbnail_max_width", legacy)
        self._thumb_h: int = config.get("thumbnail_max_height", legacy)
        self._image_exts: set[str] = set(config.get("image_extensions", [".jpg", ".jpeg", ".png"]))
        self._video_exts: set[str] = set(config.get("video_extensions", []))
        self._video_marker: str = config.get("video_marker", "")
        self._sidecar_exts: list[str] = config.get("sidecar_extensions", [".xmp", ".dop", ".pp3"])
        self._sidecar_new_extension: str = config.get("sidecar_new_extension", ".xmp")
        self._delete_empty_sidecars: bool = config.get("delete_empty_sidecars", True)
        self._schema_field_count: int = config.get("schema_field_count", 6)
        self._schema_field_titles: list[str] = config.get("schema_field_titles", [])
        self._zoom_step_percent: int = config.get("zoom_step_percent", 25)
        self._zoom_max_percent: int = config.get("zoom_max_percent", 3200)

    def _setup_table(self) -> None:
        self.setHorizontalHeaderLabels([_("Preview"), _("File name"), _("Sidecar")])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setIconSize(QSize(self._thumb_w, self._thumb_h))
        self.verticalHeader().setDefaultSectionSize(self._thumb_h + 8)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(self._THUMB_COL, QHeaderView.Fixed)
        self.setColumnWidth(self._THUMB_COL, self._thumb_w + 8)
        hh.setSectionResizeMode(self._NAME_COL, QHeaderView.Stretch)
        hh.setSectionResizeMode(self._SIDECAR_COL, QHeaderView.ResizeToContents)

        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setDragEnabled(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_directory(self, dir_path: str) -> None:
        watched = self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        self._current_dir = Path(dir_path)
        self._watcher.addPath(dir_path)
        self.refresh()

    def _on_dir_changed_on_disk(self) -> None:
        self._refresh_debounce.start()

    def refresh(self) -> None:
        if self._current_dir is None:
            return
        self._stop_worker()
        self._scan_directory()
        self._populate_table()
        self._start_worker()

    def reconfigure(self, config: dict) -> None:
        """Apply new config (thumbnail size, extensions) and refresh."""
        self._stop_worker()
        self._apply_config(config)
        self.verticalHeader().setDefaultSectionSize(self._thumb_h + 8)
        self.setColumnWidth(self._THUMB_COL, self._thumb_w + 8)
        self.setIconSize(QSize(self._thumb_w, self._thumb_h))
        self.refresh()

    def set_sidecar_filter(self, pattern: str) -> None:
        self._sidecar_filter = pattern
        self._stop_worker()
        self._populate_table()
        self._start_worker()

    def set_sort_by_date(self, value: bool) -> None:
        self._sort_by_date = value
        self._stop_worker()
        self._scan_directory()
        self._populate_table()
        self._start_worker()

    def set_sort_reverse(self, value: bool) -> None:
        self._sort_reverse = value
        self._stop_worker()
        self._scan_directory()
        self._populate_table()
        self._start_worker()

    def get_selected_files(self) -> list[Path]:
        rows = {idx.row() for idx in self.selectedIndexes()}
        return [self._display_data[r][0] for r in sorted(rows) if r < len(self._display_data)]

    def get_all_files(self) -> list[Path]:
        return [path for path, _ in self._display_data]

    def next_row_after_files(self, paths: list[Path]) -> int:
        """Return the row to select after `paths` are removed from the list.

        Counts non-removed files up to and including the last removed file's
        position — that is the index of the file that follows in the new list.
        """
        path_set = set(paths)
        rows = [i for i, (p, _) in enumerate(self._display_data) if p in path_set]
        if not rows:
            return 0
        max_row = max(rows)
        return sum(1 for i, (p, _) in enumerate(self._display_data) if i <= max_row and p not in path_set)

    def refresh_and_select(self, row: int) -> None:
        """Refresh the table then select the given row (clamped to valid range)."""
        self.refresh()
        if self._display_data:
            row = min(row, len(self._display_data) - 1)
            self.selectRow(row)
            self.scrollTo(self.model().index(row, 0))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def get_orphan_sidecars(self) -> list[Path]:
        return list(self._orphan_sidecars)

    def _is_sidecar_name(self, name_lower: str) -> bool:
        return any(name_lower.endswith(ext.lower()) and len(name_lower) > len(ext) for ext in self._sidecar_exts)

    def _scan_directory(self) -> None:
        self._file_data = []
        all_media_exts = self._image_exts | self._video_exts
        try:
            all_files = [f for f in self._current_dir.iterdir() if f.is_file()]
        except OSError:
            all_files = []

        if self._delete_empty_sidecars:
            survivors = []
            for f in all_files:
                if self._is_sidecar_name(f.name.lower()) and f not in self._sidecars_pending_edit:
                    try:
                        if f.stat().st_size == 0:
                            f.unlink()
                            continue
                    except OSError:
                        pass
                survivors.append(f)
            all_files = survivors
            self._sidecars_pending_edit = {
                p for p in self._sidecars_pending_edit if p.exists() and p.stat().st_size == 0
            }

        candidates = [f for f in all_files if f.suffix.lower() in all_media_exts]
        if self._sort_by_date:
            files = sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=self._sort_reverse)
        else:
            files = sorted(candidates, key=_natural_sort_key, reverse=self._sort_reverse)

        for f in files:
            sidecars = [f.parent / (f.stem + ext) for ext in self._sidecar_exts if (f.parent / (f.stem + ext)).exists()]
            self._file_data.append((f, sidecars))

        media_stems = {f.stem.lower() for f in candidates}
        orphans = []
        seen = set()
        for f in all_files:
            if f in seen:
                continue
            name_lower = f.name.lower()
            for ext in self._sidecar_exts:
                ext_lower = ext.lower()
                if name_lower.endswith(ext_lower) and len(name_lower) > len(ext_lower):
                    sc_stem = name_lower[: -len(ext_lower)]
                    if sc_stem not in media_stems:
                        orphans.append(f)
                        seen.add(f)
                    break
        self._orphan_sidecars = sorted(orphans, key=lambda p: p.name.lower())
        self.orphan_sidecar_count_changed.emit(len(self._orphan_sidecars))

    def _apply_filter(self) -> list[tuple[Path, list[Path]]]:
        if not self._sidecar_filter:
            return list(self._file_data)
        try:
            regex = re.compile(self._sidecar_filter, re.DOTALL | re.IGNORECASE)
        except re.error:
            return list(self._file_data)
        result = []
        for path, sidecars in self._file_data:
            if not sidecars:
                continue
            for sc in sidecars:
                try:
                    if regex.search(sc.read_text(errors="replace")):
                        result.append((path, sidecars))
                        break
                except OSError:
                    continue
        return result

    def _populate_table(self) -> None:
        self._rebuilding = True
        self._display_data = self._apply_filter()
        self.setRowCount(0)
        self.setRowCount(len(self._display_data))
        self.file_count_changed.emit(len(self._display_data))
        self.setHorizontalHeaderItem(
            self._NAME_COL,
            QTableWidgetItem(_("File name ({n})").format(n=len(self._display_data))),
        )

        placeholder = QPixmap(self._thumb_w, self._thumb_h)
        placeholder.fill(Qt.lightGray)
        font_small = QFont()
        font_small.setPointSize(9)

        for row, (path, sidecars) in enumerate(self._display_data):
            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignCenter)
            thumb_label.setFixedSize(self._thumb_w + 4, self._thumb_h + 4)
            if path.suffix.lower() in self._video_exts:
                thumb_label.setFont(QFont("", 24))
                thumb_label.setText("▶")
            else:
                thumb_label.setPixmap(placeholder)
            self.setCellWidget(row, self._THUMB_COL, thumb_label)

            self.setItem(row, self._NAME_COL, QTableWidgetItem(path.name))

            if sidecars:
                exts = "  ".join(sc.name[len(path.stem) :] for sc in sidecars)
                sc_item = QTableWidgetItem(f"● {exts}")
                sc_item.setForeground(Qt.blue)
                sc_item.setToolTip("\n".join(str(p) for p in sidecars))
            else:
                sc_item = QTableWidgetItem("○")
                sc_item.setForeground(Qt.gray)
            sc_item.setFont(font_small)
            sc_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, self._SIDECAR_COL, sc_item)
        self._rebuilding = False

    def _start_worker(self) -> None:
        if not self._display_data:
            return
        paths = [p for p, _ in self._display_data]
        self._worker = _ThumbnailWorker(paths, self._thumb_w, self._thumb_h, self._image_exts, self)
        self._worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._worker.start()

    def _stop_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        self._worker = None

    def _on_thumbnail_ready(self, row: int, image: QImage) -> None:
        widget = self.cellWidget(row, self._THUMB_COL)
        if not isinstance(widget, QLabel):
            return
        if image.isNull():
            widget.setText("?")
            return
        pixmap = QPixmap.fromImage(image)
        widget.setPixmap(pixmap.scaled(self._thumb_w, self._thumb_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _on_double_click(self, row: int, col: int) -> None:
        if row >= len(self._display_data):
            return
        path, sidecars = self._display_data[row]

        if col == self._SIDECAR_COL:
            if sidecars:
                self._open_text_sidecars(sidecars)
            elif self._sidecar_new_extension:
                new_sc = path.parent / (path.stem + self._sidecar_new_extension)
                self._sidecars_pending_edit.add(new_sc)
                new_sc.touch()
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(new_sc)))
                self.refresh_and_select(row)
        elif path.suffix.lower() in self._image_exts:
            self._show_image(path)
        elif path.suffix.lower() in self._video_exts:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_image(self, path: Path) -> None:
        if self._image_viewer is None or not self._image_viewer.isVisible():
            self._image_viewer = ImageViewer(path, self, self._zoom_step_percent, self._zoom_max_percent)
            self._image_viewer.navigate_prev.connect(lambda: self._navigate_viewer(-1))
            self._image_viewer.navigate_next.connect(lambda: self._navigate_viewer(+1))
            self._image_viewer.show()
        else:
            self._image_viewer.load_image(path)
            self._image_viewer.raise_()
            self._image_viewer.activateWindow()

    def _navigate_viewer(self, direction: int) -> None:
        rows = {idx.row() for idx in self.selectedIndexes()}
        if len(rows) != 1:
            return
        row = next(iter(rows)) + direction
        while 0 <= row < len(self._display_data):
            path, _ = self._display_data[row]
            if path.suffix.lower() in self._image_exts:
                self.selectRow(row)
                self.scrollToItem(self.item(row, self._NAME_COL))
                return
            row += direction

    def _on_selection_changed(self) -> None:
        if self._rebuilding:
            return
        if self._image_viewer is None or not self._image_viewer.isVisible():
            return
        rows = {idx.row() for idx in self.selectedIndexes()}
        if len(rows) != 1:
            self._image_viewer.close()
            return
        row = next(iter(rows))
        if row >= len(self._display_data):
            return
        path, _ = self._display_data[row]
        if path.suffix.lower() in self._image_exts:
            self._image_viewer.load_image(path)

    def viewportEvent(self, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.ToolTip and self._get_schema_fields is not None:
            item = self.itemAt(event.pos())
            if item is not None and item.column() == self._NAME_COL:
                row = item.row()
                if row < len(self._display_data):
                    path, _ = self._display_data[row]
                    preview = self._compute_preview_name(path)
                    if preview:
                        QToolTip.showText(event.globalPos(), preview, self.viewport())
                        return True
        return super().viewportEvent(event)

    def _compute_preview_name(self, path: Path) -> str:
        try:
            fields = self._get_schema_fields()
            _, parts, numeric_spec = validate_schema(fields)
            num_str = "1".zfill(len(numeric_spec)) if numeric_spec else ""
            is_video = path.suffix.lower() in self._video_exts
            if is_video and self._video_marker:
                pos = self._get_video_marker_pos() if self._get_video_marker_pos else 0
                vid_parts = list(parts)
                vid_parts.insert(min(pos, len(vid_parts)), self._video_marker)
                base_parts = vid_parts
            else:
                base_parts = list(parts)
            comps = [c for c in base_parts + ([num_str] if num_str else []) if c]
            stem = "_".join(comps)
            return f"{stem}{path.suffix.lower()}" if stem else ""
        except Exception:  # noqa: BLE001
            return ""

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        pos = self.viewport().mapFromGlobal(event.globalPos())
        row = self.rowAt(pos.y())
        if row < 0 or row >= len(self._display_data):
            event.ignore()
            return
        path, sidecars = self._display_data[row]
        menu = QMenu(self)
        infer_action = menu.addAction(_("Template"))
        delete_action = menu.addAction(_("Delete"))
        chosen = menu.exec(event.globalPos())
        if chosen == infer_action:
            self._propose_schema(path)
        elif chosen == delete_action:
            self._delete_file(path, sidecars)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            super().mouseDoubleClickEvent(event)

    def startDrag(self, supported_actions: Qt.DropActions) -> None:  # noqa: N802
        files = self.get_selected_files()
        if not files:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(f)) for f in files])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

    def _delete_file(self, path: Path, sidecars: list[Path]) -> None:
        selected = set(self.get_selected_files())
        if path in selected:
            to_delete = [(p, scs) for p, scs in self._display_data if p in selected]
        else:
            to_delete = [(path, sidecars)]

        all_files: list[Path] = []
        for p, scs in to_delete:
            all_files.append(p)
            all_files.extend(scs)

        names = "\n".join(f.name for f in all_files)
        reply = QMessageBox.question(
            self,
            _("Confirm deletion"),
            _("Permanently delete:\n{names}").format(names=names),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        next_row = self.next_row_after_files([p for p, _ in to_delete])
        dirs_to_clean: set[Path] = set()
        errors = []
        for f in all_files:
            dirs_to_clean.add(f.parent)
            try:
                f.unlink()
            except OSError as exc:
                errors.append(f"{f.name} : {exc}")

        for d in sorted(dirs_to_clean, key=lambda p: len(p.parts), reverse=True):
            self._remove_empty_parents(d)

        if errors:
            QMessageBox.warning(self, _("Deletion error"), "\n".join(errors))
        self.refresh_and_select(next_row)

    def _remove_empty_parents(self, directory: Path) -> None:
        d = directory
        while d != d.parent:
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
                    d = d.parent
                else:
                    break
            except OSError:
                break

    def _propose_schema(self, path: Path) -> None:
        proposed = self._infer_schema(path)
        if proposed is None:
            QMessageBox.information(
                self,
                _("Template"),
                _(
                    "Could not determine a template for '{name}'.\nNo part of the file name matches any field history."
                ).format(name=path.name),
            )
            return
        n = self._schema_field_count
        titles = self._schema_field_titles
        padded_titles = [titles[i] if i < len(titles) else _("Field {n}").format(n=i + 1) for i in range(n)]
        dlg = _SchemaProposalDialog(padded_titles, proposed, self)
        if dlg.exec() == QDialog.Accepted:
            self.schema_proposed.emit(proposed)

    def _infer_schema(self, path: Path) -> list[str] | None:
        """
        Try to infer schema field values from the file stem and parent directory components.
        Returns a list of n field values (empty string = empty field), or None if no match found.

        Strategy:
        - Split the stem by '_'; if the last token is all digits, treat it as the numeric field.
        - Also include the last few parent directory components as additional candidates.
        - For each candidate (in stem order then directory order), greedily assign to the
          lowest-index field whose history contains that value (monotone: index must increase).
        - For the numeric field, find the first field whose history has '#'-only entries.
        """
        n = self._schema_field_count
        all_history = load_all_history()

        field_sets: list[set[str]] = []
        for i in range(n):
            vals = set(all_history.get(f"field_{i}", []))
            vals.discard("")
            field_sets.append(vals)

        stem = path.stem
        stem_parts = stem.split("_")

        # Detect trailing numeric suffix
        numeric_raw: str | None = None
        if stem_parts and stem_parts[-1].isdigit():
            numeric_raw = stem_parts.pop()

        # Add unique directory components (up to 3 levels) as supplementary candidates
        dir_parts = [p for p in path.parent.parts[-3:] if p not in stem_parts]
        candidates = stem_parts + dir_parts

        # Greedy monotone assignment
        result = [""] * n
        last_field = -1
        matched_any = False

        for part in candidates:
            for fi in range(last_field + 1, n):
                if part in field_sets[fi]:
                    result[fi] = part
                    last_field = fi
                    matched_any = True
                    break

        # Assign numeric field
        if numeric_raw is not None:
            for fi in range(n):
                hist_list = all_history.get(f"field_{fi}", [])
                hash_entries = [v for v in hist_list if v and set(v) == {"#"}]
                if hash_entries:
                    result[fi] = "#" * max(len(v) for v in hash_entries)
                    matched_any = True
                    break

        return result if matched_any else None

    def _open_text_sidecars(self, sidecars: list[Path]) -> None:
        for sc in sidecars:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(sc)))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._refresh_debounce.stop()
        self._stop_worker()
        super().closeEvent(event)
