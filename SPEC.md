# PBPicat — Compact Spec

## Goal
Rename image/video files + their sidecars according to a structured schema.

## Sidecar files
Same stem as the image, sidecar extension appended (from config). E.g. `photo.jpg` → `photo.xmp`, `photo.prompt.txt`. Extensions may contain multiple dots. Always use `parent / (stem + ext)`, never `with_suffix`.

## Catalogs

A **catalog** is a named configuration profile stored as a subdirectory of `$XDG_CONFIG_HOME/pbpicat/`.
The active catalog's files (`settings.json`, `history.json`, `ui.conf`) are stored in that subdirectory.

| Path | Purpose |
|------|---------|
| `$XDG_CONFIG_HOME/pbpicat/catalog.conf` | Name of the last active catalog (plain text) |
| `$XDG_CONFIG_HOME/pbpicat/<name>/` | Per-catalog directory |

**Startup:** `init_catalogs()` is called before `i18n.setup()` in `__main__.py`. It:
1. Migrates any files found directly in the base directory (pre-catalog layout) into `default/`.
2. Creates `default/` only if no catalog directory exists yet.
3. Reads `catalog.conf`; validates that the named directory exists; falls back to the first available catalog.

**Rules:**
- Any catalog can be deleted, **except** the last remaining one.
- `catalog.conf` missing or pointing to a nonexistent directory → first available catalog is used.
- New catalogs start with default settings and empty history.
- Valid catalog names: letters, digits, hyphens, underscores only.
- Catalogs whose name starts with `.` or `-` are **hidden**: `list_catalogs()` excludes them by default (`include_hidden=True` to include them). Hidden from the Catalog menu and the delete-catalog list, but still counted when checking whether a name is already taken (see below).
- Switching to a hidden catalog (`set_current_catalog()`) updates the in-memory current catalog but does **not** overwrite `catalog.conf` — so on the next startup the app resumes the last non-hidden catalog, never a hidden one.

**Menus and keyboard shortcuts:**
| Menu | Item | Shortcut | Status tip |
|------|------|----------|------------|
| File | Quit | Ctrl+Q | Quit the application |
| Catalog | New catalog… | Ctrl+N | Create a new catalog |
| Catalog | Delete catalog… | — | Delete a catalog |
| Catalog | Duplicate catalog… | Ctrl+Shift+D | Duplicate the current catalog |
| Images | Open | Ctrl+O | Open selected file(s) with the default application |
| Images | Open with… | Ctrl+Shift+O | Open selected file with a chosen application |
| Images | Template | — | Infer rename template from the selected file name |
| Images | Delete | Del | Permanently delete the selected file(s) |
| Images | Rotate 90° CCW | F6 | Rotate selected image(s) 90° counter-clockwise (lossless) |
| Images | Rotate 90° CW | F8 | Rotate selected image(s) 90° clockwise (lossless) |
| Images | Rotate 180° | F7 | Rotate selected image(s) 180° (lossless) |
| Images | Apply EXIF orientation | F9 | Apply and remove EXIF orientation tag (disabled if absent) |
| Images | Force EXIF orientation to 0° | F10 | Set EXIF Orientation tag to 1 (normal) without rotating pixels (disabled if absent) |
| View | Refresh | F5 | Refresh |
| Settings | Catalog configuration… | Ctrl+, | Open catalog settings |
| Settings | History… | — | Edit field and filter history |
| Settings | Program settings… | Ctrl+Alt+, | Open program settings |
| Help | Shortcuts… | F1 | Show shortcuts window (non-modal) |
| Help | About | — | About PBPicat |

Images menu actions are disabled when no file is selected; Template is disabled with multiple selection.
Rotation actions are disabled when no image file is selected; Apply EXIF orientation and Force EXIF orientation to 0° are additionally disabled when no selected image has an EXIF orientation tag.

All actions set `setStatusTip()` so the status bar shows the description when hovering.

**Catalog menu behaviour:**
- **New catalog…** — prompts for a name, creates the directory, switches to it. If the name already exists (including hidden catalogs), asks whether to open it instead of erroring out; choosing "Open" switches to it, otherwise the action is cancelled.
- **Delete catalog…** — picks any existing visible catalog (blocked only when one visible catalog remains); if it is current, switches to the next available catalog first.
- **Duplicate catalog…** — same already-exists/open-instead behaviour as New catalog.
- Separator + dynamic list of visible catalogs (checkmark on the active one) for one-click switching.

**Window title:** Shows `[catalog_name]` after the app title when not on `"default"`.

**About dialog:** displays the application version (via `QCoreApplication.applicationVersion()`).

## Configuration (`$XDG_CONFIG_HOME/pbpicat/<catalog>/settings.json`)
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `sidecar_extensions` | list[str] | [".xmp",".dop",".pp3"] | Sidecar extensions (multi-dot supported) |
| `image_extensions` | list[str] | [".jpg",".jpeg",".png",...] | Image extensions (configurable via Images tab) |
| `video_extensions` | list[str] | [".mp4",".mov",...] | Video extensions |
| `video_marker` | str | "" | Marker inserted into video filenames at chosen position |
| `schema_field_count` | int | 6 | Number of schema fields |
| `schema_field_titles` | list[str] | [...] | Schema field titles |
| `thumbnail_max_width` | int | 128 | Max thumbnail width (px) |
| `thumbnail_max_height` | int | 128 | Max thumbnail height (px) |
| `zoom_step_percent` | int | 25 | Zoom step per click in ImageViewer (%) |
| `zoom_max_percent` | int | 400 | Max zoom in ImageViewer (%) |
| `history_max` | int | 20 | Max history size per field |
| `last_dest` | str | "" | Last destination directory used |
| `language` | str | "" | Interface language code (e.g. "fr", "en"); empty = system default |
| `sidecar_new_extension` | str | ".xmp" | Extension used when creating a new sidecar by double-clicking the sidecar column on a file with no sidecar |
| `delete_empty_sidecars` | bool | true | If true, zero-byte sidecar files (including orphans) are deleted automatically when loading a directory |
| `confirm_deletions` | bool | true | If true, show a confirmation dialog before deleting files (default Yes) |
| `delete_list_max_files` | int | 12 | When deleting more files than this threshold, show the count instead of listing file names |
| `exif_auto_rotate` | bool | true | If true, thumbnails and ImageViewer auto-rotate images according to the EXIF Orientation tag |
| `metadata_panel_side` | str | "right" | Side ("left"/"right") of the ImageViewer where the metadata panel opens |

## Rename Schema
- N editable combobox fields with per-field history
- `_` and `.` characters forbidden in any field
- Empty field = level skipped
- Field containing only `#` = numeric counter (number of `#` = minimum digits)
- Max one numeric field per schema → otherwise ValueError

### Destination path computation
```
parts    = all non-empty non-numeric fields
dirs     = parts  (all non-empty non-numeric fields form the directory tree)
prefix   = parts.join("_")
dest_dir = DEST_ROOTDIR / parts[0] / parts[1] / ...
filename = prefix[_NNN].ext  (NNN = max existing + 1, zero-padded to len("#..."))
```

For videos: marker inserted at position `video_marker_pos` among `parts` → `parts[0]_..._[MARKER_]..._parts[N][_NNN].ext`

### Examples
| Schema | Result |
|--------|--------|
| `abc`,`def`,``,`ghi`,``,`` | `ROOT/abc/def/ghi/abc_def_ghi.ext` |
| `abc`,`def`,``,`ghi`,``,`###` | `ROOT/abc/def/ghi/abc_def_ghi_001.ext` (or max+1) |
| `A`,``,`B`,`C`,`D`,`####` | `ROOT/A/B/C/D/A_B_C_D_0001.ext` |
| two numeric fields | → ValueError |

### Numbering
Max search uses **numeric** comparison (not lexicographic).
Correct order: 1, 2, 13, 101, 121 (not 1, 101, 121, 13, 2).
Images and videos have **separate** counters: each starts from `max_existing + 1` filtering only files of its own extension type.

**Fill gaps mode** (`build_rename_plan(..., fill_gaps=True)`, driven by the "Fill gaps" checkbox — see Zone 1): instead of always continuing after the max, each new number is the smallest positive integer not already used by an existing file of that type in `dest_subdir` (`renamer._used_numbers()`); once all gaps below the max are filled, numbering continues past it exactly like the default mode. Only affects "Rename all" / "Rename selection" (`build_rename_plan`), not "Renumber from 1" (`build_renumber_plan`, which already reassigns 1..N to the whole batch and never calls `find_max_number`). Files that are part of the current rename batch and already sit in `dest_subdir` (same-directory rename) are excluded from the "used" set — otherwise a file would block its own current number from being reused. Padding width behaves as today (`zfill`, not part of gap detection — `"003"` and `"3"` are the same integer).

## Main Window (4 vertical zones)

### Zone 1 — Destination
`[Label Destination:] [QLineEdit DEST_ROOTDIR] [Btn Browse] [Chk Fill gaps] [Btn Rename All] [Btn Renumber from 1]`

**Fill gaps checkbox**: unchecked by default; persisted across restarts in `ui.conf` (`schema/fill_number_gaps`, via `load_fill_number_gaps()`/`save_fill_number_gaps()`) — a session preference, deliberately **not** part of the catalog configuration (`settings.json`). See "Fill gaps mode" above for the numbering behaviour it enables.

### Zone 2 — Schema
`QFrame` with N editable `QComboBox` fields interleaved with N+1 `QRadioButton` (one before, one between each field, one after).
Radio buttons (no text, with tooltip) form a `QButtonGroup`; checked button indicates video marker position (0 = before first field, N = after last).
History persisted in `history.json`. Marker position in `ui.conf` (`schema/video_marker_pos`).
`SchemaFrame` exposes `get_fields()`, `get_video_marker_pos()`, `push_history()`, `set_fields()`, `rebuild()`.

### Zone 3 — Files (FilePanel)
`QSplitter horizontal`:
- **Left**: `DirTree` — `QTreeView` with `QFileSystemModel` (directories only). Accepts file drops from `FileListWidget` to move files into the dropped-on folder (see "Drag-and-drop move to a folder" below).
- **Right**: `FileListWidget` — QTableWidget 3 columns. Name column header shows the file count as `File name (n)`; while 2 or more rows are selected, it shows `File name (sel/n)` instead (`_update_name_header()`) — a single selected file isn't shown, since the count adds no information there.
- **Thumbnail loading is viewport-lazy**: `_start_worker()` only dispatches `_ThumbnailWorker` for rows currently visible (plus one screenful of margin above/below), not the whole directory. `_thumb_loaded: set[Path]` tracks which files already have a thumbnail (reset on each `_populate_table()`). Scrolling (`verticalScrollBar().valueChanged`) and resizing (`resizeEvent`) re-trigger `_start_worker()` through a 400 ms debounce timer (`_visible_thumbs_debounce`), so newly-visible rows get their thumbnails loaded on demand. Keeps directory load/refresh fast regardless of file count (e.g. thousands of files in one folder).
  - The 400 ms debounce specifically targets mouse-wheel/keyboard scrolling: each wheel notch fires `valueChanged`, and if consecutive notches are spaced further apart than the debounce interval, each pause triggers a load for that transient position. Scrolling a long distance with the wheel means passing through (and pausing within) many more such intermediate positions than a single scrollbar-drag jump, so the number of triggered batches — and thus perceived lag — scales with distance travelled, not with the destination row itself (jumping directly to any row via drag-and-release stays fast regardless of position, since it's a single settle point).
  - While the scrollbar handle is actively being dragged (`isSliderDown()`), the debounce is a no-op — loading only happens once via `sliderReleased`, otherwise a slow/paused drag across a long list would trigger a load at every intermediate position along the way.
  - Restarting the worker on scroll/resize uses `_cancel_worker_async()` (cancel flag + `deleteLater` on `finished`, no blocking `wait()`), not `_stop_worker()`: rows/paths stay valid since the table isn't rebuilt, so a stray `thumbnail_ready` from the just-cancelled thread is harmless, and the GUI thread never stalls waiting for a large in-flight JPEG decode — important since mouse-wheel scrolling naturally re-triggers the debounce many times over a long scroll session. `_stop_worker()` (blocking) is still used wherever `_populate_table()` follows (directory/filter/sort changes/catalog switch).
  - `_stop_worker()`'s blocking `wait()` only guarantees the worker thread has stopped *running* — it cannot un-post a `thumbnail_ready` event already queued (cross-thread `AutoConnection`) at the moment cancellation was noticed, since a worker only checks its cancel flag between files, not mid-decode. Such a stale signal can still be delivered *after* `_populate_table()` has rebuilt the table for a new directory/catalog, with a row index that now points at a completely unrelated file. `thumbnail_ready` therefore carries the path it was decoded for (not just the row), and `_on_thumbnail_ready()` discards the signal unless `self._display_data[row][0]` still equals that path — otherwise it would both paint the wrong image and wrongly mark the new file's path as already-loaded in `_thumb_loaded`, permanently starving it of its real thumbnail (viewport-lazy loading treats `_thumb_loaded` as the sole "already have it" gate, so nothing else would ever re-request it for that table's lifetime).
  - The pending batch (visible rows + margin not yet in `_thumb_loaded`) is split across up to 4 concurrent `_ThumbnailWorker` instances (`self._visible_workers`, capped by `os.cpu_count()`), instead of one worker decoding the whole batch sequentially — cuts wall-clock time for a freshly-scrolled-to batch roughly by the number of cores used. `self._worker` (singular) remains dedicated to `refresh_thumbnails_for_paths()`'s targeted subset reload; `_stop_worker()`/`_cancel_worker_async()` handle both.
  - `image_io.py`'s `load_qimage()` (called by `_ThumbnailWorker`, off the GUI thread) and `load_pixmap()` (called by `ImageViewer.load_image()`, on the GUI thread) serialize their `QImageReader` decode behind a shared `threading.Lock` (`_qimage_reader_lock`): Qt's image-format plugins deadlock if invoked concurrently from more than one thread, which reliably froze the app when a rename's `refresh_and_select()` reloaded the viewer's image on the GUI thread at the same moment `_start_worker()` was decoding thumbnails for the same refresh in the background.

#### Keyboard navigation between panels
| Location | Key | Effect |
|----------|-----|--------|
| DirTree / FileListWidget | Tab / Shift+Tab | Toggle focus between the two panels (`event()` override intercepts `Key_Tab`/`Key_Backtab` before Qt's focus-chain machinery) |
| DirTree | ← ↑ → ↓ | Directory navigation only (native `QTreeView`); no focus transfer |
| DirTree / FileListWidget | Home / End | Go to first / last entry |
| FileListWidget | ↑ / ↓ | Move selection to previous / next row (native) |
| FileListWidget | ← / → | Swallowed (no-op) — only Up/Down move the selection |
| FileListWidget | Return / Enter | Opens the current row in the image viewer (images and videos); with a multi-row selection the viewer opens on the current row with the selection strip; no effect on sidecar column |

`FileListWidget` Home/End are handled explicitly (`selectRow(0)` / `selectRow(last)` + `scrollToItem`) because a `QTableWidget` would otherwise move the cursor within the row's columns. `DirTree` Home/End are native.

When `FileListWidget` receives focus and has no selected row, row 0 is selected automatically.

#### FileListWidget
| Col | Content | Double-click / Return | Hover |
|-----|---------|--------------|-------|
| Preview | Async thumbnail (QThread) or `resources/movie.svg` icon (scaled/centered via `QIcon.pixmap`, keeps aspect ratio) for video | Opens/activates the ImageViewer, image or video (`_show_in_viewer()`) | — |
| Name | Filename | Opens/activates the ImageViewer, image or video (`_show_in_viewer()`) | Tooltip: previewed final name (number = 1) |
| Sidecar | `●` + extensions if present, `○` otherwise | One sidecar: opens it (`open_default`). Several sidecars: `QMenu` chooser at `QCursor.pos()`, one entry per sidecar filename, opens only the picked one. No sidecar: creates `<stem><sidecar_new_extension>` (empty `touch()`, tracked in `_sidecars_pending_edit`) and opens it (`open_default`). | — |

Return/Enter acts like a double-click on the Name column of the current row (ignores the sidecar logic); it works for a single or multi-row selection — a multi-row selection opens the viewer on the current row with the selection strip, exactly like a Shift+double-click.

Multi-selection (ExtendedSelection).

**Auto-selection after action:**
- After renaming: selects the file that immediately followed the last renamed file in the new list (or the last file if nothing follows). ImageViewer stays open and updates.
- After deleting: selects the file that was next after the deleted one (or the last file if it was the last). ImageViewer stays open and updates.
- After a directory change (`load_directory`): selects the first image in the directory, if any (`_select_first_image()`). An already-open ImageViewer follows and loads it (selection happens outside the `_auto_selecting` guard used for the table rebuild itself, so the normal `itemSelectionChanged` → viewer-update path runs).
- Startup: the restored directory is scrolled into view in the dir tree.

**Context menu (right-click on a file):**
- **Open** (Ctrl+O): opens the file with the default application via `platform.open_default`.
- **Open with…** (Ctrl+Shift+O): shows an application chooser dialog (Linux: `gio mime` + `.desktop` scan over the XDG app dirs — `$XDG_DATA_HOME` then each `$XDG_DATA_DIRS` entry, `/applications` appended, deduped; app labels use the `.desktop` `Name[<lang>]=` key for `i18n.current_language()` (exact locale → bare language → unlocalized `Name=`), read from the `[Desktop Entry]` group only; macOS: app name prompt; Windows: "Open as" dialog).
  - Linux: the list is ordered per MIME type as a most-recently-used list persisted in `open_with.json` (`_order_by_lru()`): apps used before, still registered, come first in MRU order; apps that appeared since last run are appended in system order; apps that vanished are dropped. On confirmation, `_remember_choice()` rewrites that MIME's list with the picked `.desktop` at the front followed by the other still-available apps. A missing, unparseable, or wrong-shaped `open_with.json` is treated as an empty mapping (`load_open_with_lru()`), never an error.
- **Template**: infers field values from the file stem and parent directory components, by matching against field histories. Shows a confirmation dialog; if confirmed, applies values via `SchemaFrame.set_fields()` (without pushing to history). If no match found, shows an info message.
- **Delete** (Del): permanently deletes the file and its sidecars (confirmation dialog if `confirm_deletions=true`). If the right-clicked file is among the selection, all selected files (and their sidecars) are deleted together. After deletion, empty source directories are removed recursively up the tree. Selects the next file automatically.
- **Rotate 90° CCW / CW / 180° / Apply EXIF / Reset EXIF**: rotation actions (see below).

Same actions available in the **Images** menu and in the **ImageViewer** toolbar (rotation buttons between zoom and action buttons).

**Rotation actions** (`image_ops.py`):
- JPEG lossless rotation: shells out to `jpegtran` (libjpeg-turbo). If absent, a dialog explains the requirement.
- Before invoking `jpegtran`, JPEG bytes are passed through `repair_jpeg_sos()`, which fixes a malformed SOS header (`Se=0` instead of the mandatory `63` for baseline JPEGs) seen in some camera firmware (e.g. certain Samsung front-camera modules); without this, `jpegtran` fails with "Invalid SOS parameters for sequential JPEG". Same repair is applied in `image_io.py` before handing JPEG bytes to Qt's decoder, to avoid the same warning and ensure `setAutoTransform` (EXIF auto-rotation) works. No-op (byte-identical) for well-formed files.
- `qt.gui.imageio.jpeg` Qt logging category is silenced at startup (`__main__.py`): other malformed-JPEG warnings (e.g. "Corrupt JPEG data: N extraneous bytes before marker 0xd9", trailing garbage before EOI) have no safe automatic fix but no practical impact either — Qt/Pillow decode these files fine.
- `image_io.py`'s `_make_reader()` raises `QImageReader.setAllocationLimit()` from Qt's default (256 MiB) to 1024 MiB (`_ALLOCATION_LIMIT_MIB`). The default is checked against the *undecoded* image's declared dimensions — a 50-100 MP phone photo decodes to 200-400 MB as RGB32, exceeding it — causing Qt to reject the read outright ("Rejecting image as it exceeds the current allocation limit") and forcing a much slower full-resolution Pillow fallback (`load_qimage()`/`load_pixmap()`'s `except` branch) just to display or thumbnail the file. Thumbnail generation (which always calls `setScaledSize()` before `read()`) is unaffected regardless of source size — Qt's check there applies to the *scaled* target, not the source — so this specifically matters for `load_pixmap()` (full-size image viewer).
- If `jpegtran` fails for another reason (e.g. "Premature end of JPEG file" on a genuinely truncated file, such as some panorama shots missing trailing data), `_jpegtran_error_hints()` prepends a user-friendly explanation to the raw `jpegtran` message when a known pattern matches. `RuntimeError`/`QMessageBox` for both rotation and undo failures are prefixed with the file name so the user knows which file is at fault.
- Batch rotation (`_rotate_images()`): a failure on one file does not stop the batch — processing continues for the remaining selected files. Errors are reported via a single `QMessageBox` with a short summary ("N file(s) could not be rotated.") and the full per-file list in `setDetailedText()` (collapsible, scrollable) — avoids an unusably tall dialog when rotating a large selection (e.g. thousands of files) where many fail for the same reason.
- Other formats (PNG, TIFF, BMP, WebP): uses Pillow (`rotate`, `transpose`). Always lossless for these formats.
- After JPEG rotation, the EXIF Orientation tag is stripped using `pyexiv2` (`set_exif_orientation()`; no-op if the file has no EXIF block at all).
- All rotations and EXIF resets are **undoable**: pushed to the undo stack as `("rotation", [(path, undo_op, orig_orient)])` or `("reset_exif", [(path, orig_orient)])`. Undo button label changes accordingly.
- **Apply EXIF orientation**: reads the EXIF Orientation tag, applies the corresponding transform (rotation or flip), then strips the tag. Works for all 8 EXIF orientation values. Disabled in the UI when the image has no orientation tag.
- **Force EXIF orientation to 0°**: sets the EXIF Orientation tag to 1 (normal) without rotating pixels. Disabled in the UI when the image has no orientation tag.
- **Viewer sync**: `refresh_thumbnails_for_paths()` (called after every rotation/EXIF-reset, including their undo) also reloads an open ImageViewer's image if its `current_path` is among the affected paths — whether the rotation was triggered from the viewer's own toolbar or from the main window (menu/context menu/shortcuts).

### Zone 4 — Buttons
`[Btn Undo last rename] [stretch] [ComboBox Sidecar filter] [stretch] [Btn Rename selection]`

**Rename selection** has an `F2` shortcut (`QPushButton.setShortcut()`), in addition to the click. Unlike a click, a shortcut doesn't steal keyboard focus from the file list — clicking the button used to leave the file list unable to receive further arrow-key navigation until it regained focus. `refresh_and_select()` also explicitly calls `setFocus()` on the file list after re-selecting the row, as a defensive measure.
- **Selection-restore methods must set the current index, not just the selection**: table rebuilds (`refresh()`/`_populate_table()`) invalidate both `currentIndex()` and the selection. `_select_paths_and_set_current(paths)` is the single place that restores selection-by-path after such a rebuild: it selects every row whose path is in `paths` via `selectionModel().select(index, Select | Rows)`, then — critically — also calls `selectionModel().setCurrentIndex(index, NoUpdate)` for the first match, since `select()` alone only adds to the *selection* and never moves the *current index*. `_refresh_preserve_selection()` and `refresh_and_select_paths()` both call it instead of duplicating the loop. Without the `setCurrentIndex()` step, `currentIndex()` stayed invalid (-1) even though a row was visibly selected, so the next arrow-key press navigated as if starting from row 0 — reproduced by renaming a file via the `F2` shortcut: `execute_rename()`'s disk change fires `QFileSystemWatcher.directoryChanged` shortly *after* `refresh_and_select()`'s own refresh already ran, restarting the 400 ms debounce (`_on_dir_changed_on_disk` → `_refresh_debounce`) and triggering a second, redundant `_refresh_preserve_selection()` call that hit this bug.

**Sidecar filter**: editable QComboBox with history. Python regex applied to sidecar file content (re.DOTALL | re.IGNORECASE). Only files having at least one matching sidecar are shown; files with no sidecar are hidden when filter is active. History persisted in `history.json` under key `sidecar_filter`.

**Renumber from 1**: renames all displayed files in-place (same directory), assigning sequential numbers starting from 1 according to the current schema's numeric field. Images and videos have separate counters. Requires a numeric field (`#`) in the schema. Uses two-phase rename (via temp names) to avoid circular conflicts. Result enters the undo stack like a regular rename. If all files are already correctly numbered, shows a status message without prompting.

**Drag-and-drop move/copy to a folder**: dragging selected files from `FileListWidget` and dropping them onto a directory row in `DirTree` (`dragEnterEvent`/`dragMoveEvent`/`dropEvent`, `setAcceptDrops(True)` + `DropOnly` mode) moves — or copies, see below — the files and their sidecars into that folder, keeping their names unchanged (destination path is `dest_dir / src.name`, not passed through the rename schema). `mime.setUrls()` only ever carries the *main* file paths, never sidecars — dragging a selection out to another application (e.g. to paste a path into a terminal) hands over just those names; sidecars are only resolved when the drop lands back inside this app's own `DirTree`.

- **Action mapping (`FileListWidget.startDrag()`)**: `drag.exec(Qt.CopyAction | Qt.MoveAction, Qt.MoveAction)` — both actions declared supported, `Qt.MoveAction` as the default (no modifier held), so Qt's native platform drag backend live-tracks Ctrl/Shift for the whole duration of the drag and updates the cursor accordingly by itself. This follows Qt's own cross-platform modifier convention (Ctrl → copy, Shift → move, Ctrl+Shift → link) rather than a custom one: that mapping is baked into the platform's native DnD backend (X11/Wayland/OLE) and isn't exposed for the application to override — reading `QApplication.keyboardModifiers()` once at drag-start and locking a single action for `drag.exec()` was tried first, but that silently drops the native cursor feedback and any modifier changes made mid-drag, since only one action is ever offered.
- **Cursor pixmap**: `drag.setDragCursor(get_cursor_pixmap(name), action)` before `exec()` for all three of `Qt.CopyAction` ("copy"), `Qt.MoveAction` ("move"), and `Qt.IgnoreAction` ("not-allowed", shown over widgets that don't accept the drop) — several window managers/compositors don't render Qt's built-in per-action drag cursors distinctly (or at all), so without explicit pixmaps the cursor can look identical regardless of the negotiated action/target. `icons.get_cursor_pixmap()` (`icons.py`) loads the PBIcons `{name}@2x.png` asset from `resources/` (synced via `tools/update_icons.py`, `_CURSOR_FILES`) and calls `setDevicePixelRatio(2.0)` on it, so the cursor renders crisp on both standard and HiDPI screens regardless of the actual screen scale factor.
- **Internal drop** (`event.source() is self._file_list`, i.e. dragged from this app's own file list): `Qt.MoveAction` → `FileListWidget.move_files_to()`, `Qt.CopyAction` → `FileListWidget.copy_files_to()`. Both resolve `(path, sidecars)` pairs from `_display_data` (`_internal_drop_entries()`) and build the same `(src, dst)` plan shape. `move_files_to()` reuses `execute_rename()`/`undo_rename()` and removes the moved rows via `_delete_rows_and_select()` (no thumbnail regeneration for the remaining rows) since the files leave the currently-displayed directory. `copy_files_to()` reuses the new `execute_copy()`/`undo_copy()` (`renamer.py`, `shutil.copy2` based, same atomic pre-check-all-destinations-first pattern as `execute_rename`) and leaves the table alone — the copies land in a *different* folder than the one being displayed (`_internal_drop_entries()` already excludes same-directory drops), so nothing needs to disappear or reappear in the current view. Both emit their `files_moved(plan)` / `files_copied(plan)` signal on success; `MainWindow._on_files_moved()` / `_on_files_copied()` push `("move", plan)` / `("copy", plan)` onto `_undo_stack`. Dropping onto the files' own current directory, or a target that already has a same-named file, is a no-op / reports a "Move error"/"Copy error" respectively.
- **External drop** (`event.source()` is not the app's own `FileListWidget` — `None` for a drag from another process, e.g. a file manager): routed the same way by `event.proposedAction()`, but to `FileListWidget.move_external_files_to()` / `copy_external_files_to()` instead — these resolve sidecars by scanning disk via `self._sidecar_exts` (external paths aren't in `_display_data`) and skip non-existent paths/directories and files already located in the destination. `move_external_files_to()` reuses `execute_rename()`; `copy_external_files_to()` pre-checks for name conflicts (aborts entirely if any destination already exists) then copies file-by-file with `shutil.copy2()`, collecting per-file `OSError`s into a single warning instead of aborting (a partial copy is possible on disk/permission errors, same trade-off as `_delete_file`). If the destination folder is the one currently displayed, `_refresh_preserve_selection()` shows the new/copied files. **Neither external path is added to `_undo_stack`** — they emit `files_moved_external(plan)` / `files_copied_external(plan)` instead, and `MainWindow._on_external_files_moved()` / `_on_external_files_copied()` only show a status message (`"{n} file(s) moved."` / `"{n} file(s) copied."`), no undo push. Only *incoming* external drops are handled this way — dragging *out* to another application never triggers any file operation on this app's side, regardless of which action ends up negotiated (the `QDrag.exec()` return value is ignored): the target application is solely responsible for what it does with the file paths it receives.

#### ImageViewer (`ui/image_viewer.py`)
Non-modal window opened by double-clicking the preview column.
Toolbar (left→right): **Fit** | **1:1** | **Width** | **Height** | sep | **+** | **−** | sep | **↺** | **↻** | **↕** | **EXIF** | **0°** | sep | **Open** | **Open with** | **Template** | **Delete** | sep | **Metadata** (checkable) | stretch | zoom label.
The **EXIF** (Apply EXIF orientation) and **0°** (Force EXIF orientation to 0°) buttons are disabled when the loaded image has no EXIF orientation tag.
Icons: FreeDesktop theme → `resources/zoom_*.svg` → text fallback.
Action buttons emit signals (`open_requested`, `open_with_requested`, `template_requested`, `delete_requested`) connected to `FileListWidget` handlers — resolved against `ImageViewer.current_path` (the file actually displayed), not the table's row selection, so they stay correct after Left/Right selection-strip navigation.
| Key | Action |
|-----|--------|
| 0 / X | Fit window (default) |
| 1 / Z | Actual size (1:1) |
| W | Fit width |
| H | Fit height |
| + / − | Zoom in / out (also numpad) |
| ↑ / ↓ | Navigate prev/next media file (single-selection only) |
| ← / → | Navigate within the current multi-file selection (only active when 2+ files are selected) |
| Del | Delete current image and sidecars |
| I | Toggle metadata panel |
| Escape | Close window |

Mouse gestures: **double-click** centers the viewport on the clicked point; **Ctrl+left-click** zooms in centered on the clicked point; **Ctrl+right-click** zooms out centered on the clicked point (both CUSTOM mode).
When switching zoom mode or loading a new image, the viewport is centered; in CUSTOM mode, scroll position is preserved proportionally.

**Video display**: `ImageViewer.display(path)` dispatches by extension (`video_extensions` ctor kwarg) to `load_image()` or `show_video()`. `show_video()` shows the `movie` icon (`get_icon("movie")`) scaled/centered like Fit-window zoom, and locks the viewer in "video mode": the 4 zoom-mode buttons, zoom in/out, and the 3 rotate buttons + EXIF/0° buttons are all disabled, the zoom mode is forced to `FIT_WINDOW` (`_set_mode`/`_apply_custom`/`_zoom_to_point` all no-op while `_video_mode` is set, except re-selecting Fit window itself), and the zoom label is blank. Returning to an image via `load_image()` restores normal control state.

**Multi-file selection**: `ImageViewer.set_selection(paths, current=None)` — called by `FileListWidget._on_selection_changed()` on every selection change and by `_show_in_viewer(path, selection=...)` on double-click, which passes the full current table selection with `current=path` so a Shift+double-click that keeps a multi-row selection displays/highlights the double-clicked file rather than resetting to the first row. `current` not in `paths` (or omitted) falls back to `paths[0]`. `_on_selection_changed()` picks `current` so that **extending the selection displays the freshly added file**: it passes the table's current row when that row is in the selection, otherwise the viewer's own `current_path` (a `@property`, not a callable) when it is still selected — so removing an unrelated row from a multi-selection leaves the displayed image unchanged — otherwise `None` (→ `paths[0]`). With 2+ paths, a horizontal thumbnail strip (`_SelectionStrip`, `QScrollArea`) appears along the full width of the window, below the splitter (outside it, in the outer `QVBoxLayout`, so the metadata panel just gets less vertical space and its own `QTextBrowser` scrolls as needed) — the currently displayed file is highlighted with a solid border (`_STRIP_HIGHLIGHT_STYLE`) and kept scrolled into view. Clicking a thumbnail (`_ClickableLabel`, `thumbnail_clicked` signal → `_act_selection_goto()`) jumps straight to that file. Left/Right move `_selection_index` within `_selection_paths` (clamped, no wraparound) the same way; both paths are entirely internal to `ImageViewer` — they never touch the file list's table selection. Up/Down (`navigate_prev`/`navigate_next` → `FileListWidget._navigate_viewer()`) naturally become inert during a multi-selection since that handler already requires exactly one selected table row. With a single file selected, the strip is hidden.

**Metadata panel** (`ui/metadata_panel.py`, checkable **Metadata** toolbar button, own separator group — deliberately set apart from the other groups):
- A `QSplitter(Qt.Horizontal)` holds the image `QScrollArea` and a `MetadataPanel` (read-only `QTextBrowser`, HTML-formatted). Side (`metadata_panel_side` config, "left"/"right") picks the widget order; `ImageViewer.set_metadata_panel_side()` reorders it live if the setting changes while the viewer is open (`FileListWidget.reconfigure()`).
- **Lazy**: metadata is only read (`pbpicat.metadata.read_metadata()`) while the panel is visible — toggling it off clears the panel and no read happens on the next `load_image()`/navigation until toggled back on. Avoids the memory/time cost of parsing EXIF/IPTC/XMP for images the user never inspects.
- Sections rendered (each omitted if empty): **File** (name, human size, pixel dimensions via `image_io.image_size()`) | **EXIF** | **IPTC** | **XMP** (embedded, via `pyexiv2.Image.read_exif/read_iptc/read_xmp`) | **XMP (sidecar)** — read from the image's `.xmp` sidecar if one exists among `sidecar_extensions` (`metadata.find_xmp_sidecar()`, same `parent / (stem + ext)` convention as elsewhere). Tag keys have their EXIF/Iptc/Xmp family prefix stripped for readability.
- Panel visibility and splitter sizes persist across viewer sessions in `app.conf` (`image_viewer/metadata_panel_visible`, `image_viewer/metadata_splitter_state`), independent of per-image window geometry.
- Setting: **Settings → Catalog configuration… → Images** tab, "Metadata panel side" combo (Left/Right).

## Rename Logic (`src/renamer.py`)
1. `validate_schema(fields)` → `(dirs, parts, numeric_spec)` or `ValueError`
2. `find_max_number(dest_dir, basename, extensions=None)` → int (numeric comparison)
3. `build_rename_plan(dest_root, fields, sources, sidecar_exts, img_exts, video_exts, video_marker, video_marker_pos)` → `[(src, dst), ...]`
4. `execute_rename(pairs)`:
   - Pre-check: if any dst exists → `FileExistsError` (nothing moved)
   - Move + create missing directories
   - Rollback on intermediate error
   - Delete empty source directories

## Dialogs

### SettingsDialog (`ui/settings_dialog.py`)
Menu **Settings → Catalog configuration…** (Ctrl+,) — tabs:
- **Rename Schema**: QSpinBox (field count 1–12) + dynamic QFormLayout (titles); max history and max deletion list size
- **Sidecar Extensions**: QListWidget + add/delete (multi-dot extensions supported); QComboBox "Default extension for new sidecar" populated from the list; "Delete empty sidecar files" checkbox
- **Images**: QListWidget + add/delete for recognized image extensions; zoom step (%) and max zoom (%) for ImageViewer; "Metadata panel side" combo (Left/Right) — controls `metadata_panel_side`; "Confirm deletions" checkbox (default checked); "Apply EXIF rotation" checkbox (default checked) — controls `exif_auto_rotate`
- **Video**: QListWidget extensions + marker field
- **Thumbnails**: max width/height
- OK → `save_config()` + `schema_frame.rebuild(config)`

### GlobalSettingsDialog (`ui/settings_dialog.py`)
Menu **Settings → Program settings…** (Ctrl+Alt+,) — tabs:
- **Sidecar Extensions**: default extensions for new catalogs (stored in `global_settings.json`)
- **Language**: QComboBox (system default + available locales); restart required
- OK → `save_global_config()`

### HistoryDialog (`ui/history_dialog.py`)
Menu **Settings → Histories…**
- QTabWidget: one tab per field
- Per tab: QListWidget with internal drag-and-drop + Move Up / Move Down / Sort ↓ (ascending) / Sort ↑ (descending) / Delete / Clear All buttons. Sort buttons enabled only with ≥2 items; arrows denote the visual direction of the resulting list, not conceptual sort direction.
- Sort comparison: `_sort_fold()` folds each string (OE-ligature → "oe"/"OE" via explicit translation table, then NFKD + strip combining marks for diacritics, then `casefold()`) before comparing with a `QCollator(QLocale(i18n.current_language()))` — locale-aware, case- and diacritic-insensitive (`O=o=Ô=Ǫ`, `Œ=OE=œ`). Empty-string entries are always placed last, in both ascending and descending order.
- OK → `save_all_history()` then `schema_frame.rebuild(config)` to reload combos

## Persistence
| Data | File |
|------|------|
| Active catalog name | `$XDG_CONFIG_HOME/pbpicat/catalog.conf` |
| App config + `last_dest` | `$XDG_CONFIG_HOME/pbpicat/<catalog>/settings.json` |
| Field histories + sidecar filter history | `$XDG_CONFIG_HOME/pbpicat/<catalog>/history.json` |
| Last source dir (`source/last_dir`), video marker pos (`schema/video_marker_pos`) | `$XDG_CONFIG_HOME/pbpicat/<catalog>/ui.conf` (QSettings IniFormat) |
| Window geometry for all windows except About; ImageViewer metadata panel visibility (`image_viewer/metadata_panel_visible`) and splitter state (`image_viewer/metadata_splitter_state`) | `$XDG_CONFIG_HOME/pbpicat/app.conf` (QSettings IniFormat, via `app_qsettings()`) |
| Program-level settings (default sidecars, language) | `$XDG_CONFIG_HOME/pbpicat/global_settings.json` |
| "Open with…" per-MIME MRU `.desktop` lists (Linux) | `$XDG_CONFIG_HOME/pbpicat/open_with.json` (catalog-independent; `load_open_with_lru()`/`save_open_with_lru()`) |

`$XDG_CONFIG_HOME` defaults to `~/.config` if unset.
`config.py` handles one-shot migration from legacy QSettings if `history.json` is absent.
`init_catalogs()` handles one-shot migration from pre-catalog flat layout (files directly in base dir → `default/`).
`--dev-config-dir DIR` CLI flag overrides `_BASE_DIR` before `init_catalogs()` via `set_base_dir()`.
Optional positional CLI arg `catalog` (name, not path; may be hidden — for a leading `-`, pass it after `--`, e.g. `pbpicat -- -secret`): after `init_catalogs()` + `i18n.setup()`, if it names an existing catalog (`list_catalogs(include_hidden=True)`), switches to it via `set_current_catalog()`; otherwise shows a `QMessageBox` warning and falls back to the normal startup catalog (unchanged behaviour).

## Internationalisation
`src/pbpicat/i18n.py` — call `i18n.setup(app)` once before creating any window.
- Uses `gettext` + a `QTranslator` bridge (`_GettextTranslator`).
- Also loads `qtbase_<lang>.qm` via `QLibraryInfo.TranslationsPath` so Qt's built-in strings (standard button labels: OK, Cancel, Close, Yes, No…) are translated.
- `.mo` files in `src/pbpicat/locale/<lang>/LC_MESSAGES/pbpicat.mo`.
- Locales: `en`, `fr`, `de`, `es`, `it`, `ru`, `vi`, `zh_CN`.
- Language resolved: config `language` key → system env vars → `locale.getlocale()` → "en".
- `available_languages()` scans `.mo` files; `language_name` msgid holds the native name.
- All UI strings wrapped in `_()` (installed by `gettext.NullTranslations.install()`).
- Key names localised via `QKeySequence.toString(NativeText)` (e.g. Del → Suppr, Esc → Échap on FR keyboards); mouse button names translated via gettext.

## Distribution (`pbpicat.spec`)
PyInstaller one-file build; artifact named `PBPicat-<version>-<os>-<arch>`.
`.mo` files, all `resources/*.svg`, and the package `dist-info` (via `copy_metadata("pbpicat")`) bundled as datas; the dist-info is required so `importlib.metadata.version("pbpicat")` works at runtime.
`pyexiv2/lib/*.{so,dylib,dll,pyd}` bundled explicitly as binaries (into `pyexiv2/lib/`): pyexiv2 loads these via `ctypes.CDLL()` with a runtime-built path, invisible to PyInstaller's static analysis.
macOS builds as `.app` bundle.
Version string: `tools/git_version.sh` locally (exact tag + clean tree → `x.y.z`, else `dev`);
CI reads `github.ref_name` and sets `PBPICAT_VERSION` before calling PyInstaller.
`make dist` runs `pixi install` first to ensure the editable install matches `pyproject.toml`.
Build via: `make dist`

## File Structure
```
PBPicat/
├── Makefile
├── pbpicat.spec
├── pyproject.toml         # includes [tool.pixi.*] env/tasks config
├── pixi.lock
├── SPEC.md
└── src/pbpicat/
    ├── __main__.py        # CLI arg parsing (--dev-config-dir, optional positional catalog name, + Qt flags via argparse_qt); calls init_catalogs() then i18n.setup(app), optionally switches catalog, before creating MainWindow
    ├── argparse_qt.py     # add_qt_arguments(parser): Qt flags as --double-dash options, collected in args.qt_args
    ├── config.py          # catalog mgmt + load/save config+history (JSON), qsettings() → ui.conf, app_qsettings() → app.conf, load/save_open_with_lru() → open_with.json
    ├── i18n.py            # gettext bootstrap
    ├── renamer.py         # pure logic (no Qt)
    ├── image_io.py        # load_qimage/load_pixmap/image_size (Qt decode, shared QImageReader lock)
    ├── image_ops.py       # lossless rotation + EXIF orientation get/set (pure logic, no Qt)
    ├── metadata.py         # EXIF/IPTC/XMP + XMP-sidecar reading via pyexiv2 (pure logic, no Qt)
    ├── locale/            # en fr de es it ru vi zh_CN
    │   └── <lang>/LC_MESSAGES/pbpicat.{po,mo}
    ├── resources/
    │   ├── pbpicat.svg
    │   └── zoom_{fit,original,width,height,in,out}.svg
    ├── platform/
    │   ├── __init__.py       # dispatches to _linux / _macos / _windows at import time
    │   ├── _linux.py         # XDG: xdg-mime, gio, gtk-launch, .desktop file parsing, per-MIME MRU app ordering
    │   ├── _macos.py         # subprocess open -a
    │   └── _windows.py       # os.startfile / os.startfile(…, "openas")
    └── ui/
        ├── main_window.py
        ├── schema_frame.py       # SchemaFrame: get_fields / set_fields / push_history / rebuild
        ├── settings_dialog.py    # SettingsDialog (5 tabs) + GlobalSettingsDialog (2 tabs)
        ├── history_dialog.py     # HistoryDialog
        ├── file_panel.py
        ├── dir_tree.py
        ├── file_list_widget.py   # FileListWidget + _ThumbnailWorker + Open/OpenWith/Template/Delete context menu
        ├── image_viewer.py       # Open/OpenWith/Template/Delete signals + toolbar buttons + metadata panel splitter
        └── metadata_panel.py     # MetadataPanel: QTextBrowser rendering metadata.read_metadata() as HTML
```
