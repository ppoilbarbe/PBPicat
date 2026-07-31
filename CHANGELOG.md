# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.16.0] - 2026-07-31

### Added

- **File list: image resolution and human-readable file size shown under the file name** — e.g. `1920×1080  ·  32.5 KB`. File size appears as soon as a directory loads; resolution is read from the image header only (no full decode) and piggybacks on the existing lazy thumbnail worker, so it stays cheap even for large directories. Both are refreshed after a rotation, so a 90°/270° rotation's width/height swap and the file's new size are reflected immediately.
- **File list: the first image of a directory is now auto-selected when switching directories** (if the directory contains one) — an already-open image viewer follows the new selection and displays it.
- **"Fill gaps" checkbox** next to the destination field — when checked, "Rename all" / "Rename selection" assign the smallest missing number in the existing sequence (per image/video counter) instead of always continuing after the current max; once all gaps are filled, numbering continues past the max as before. Does not affect "Renumber from 1", which already reassigns the whole batch from scratch. Unchecked by default; the choice is a session preference persisted across restarts (`ui.conf`), deliberately kept out of the catalog configuration (`settings.json`).

### Fixed

- **Rotating an image (90°/180°/270°, "Apply EXIF orientation", or "Force EXIF orientation to 0°") did not update an already-open image viewer showing that image** — whether triggered from the viewer's own toolbar or from the main window (menu, context menu, or shortcut), the viewer kept displaying the stale, unrotated pixels; only the file list's thumbnail was refreshed. `refresh_thumbnails_for_paths()` (called after every rotation/EXIF-reset, including undo) now also reloads the viewer's image when it is showing one of the affected files.

## [1.15.0] - 2026-07-24

### Added

- **`F2` shortcut for the "Rename selection" button** — clicking the button moved keyboard focus away from the file list, preventing further arrow-key navigation until it regained focus; a shortcut triggers the action without stealing focus. Also added to the shortcuts window (F1) and to the button's tooltip.
- **Hidden catalogs** — catalogs whose name starts with `.` or `-` are now excluded from the Catalog menu and the "Delete catalog…" list. `list_catalogs()` gained an `include_hidden` keyword argument (default `False`) to opt into seeing them. Switching to a hidden catalog no longer overwrites `catalog.conf`, so restarting the app always resumes the last non-hidden catalog rather than a hidden one.
- **Optional positional CLI argument to load a specific catalog at startup** — `pbpicat <name>` (may be a hidden catalog; a name starting with `-` must be passed after `--`, e.g. `pbpicat -- -secret`). If no catalog with that name exists, a warning dialog is shown and startup falls back to the normal behaviour (last opened catalog).
- **"Sort ↓" / "Sort ↑" buttons in the history edit windows** (`Settings → Histories…`) alongside the existing Move up/down — sort ascending/descending, locale-aware (`QCollator` using the interface's display language) and insensitive to case and diacritics (`O=o=Ô=Ǫ`, `Œ=OE=œ`). Disabled when fewer than 2 items are in the list. Empty-string entries always sort to the end, regardless of direction.

### Changed

- **"New catalog…" / "Duplicate catalog…" — name already taken** — previously just showed a blocking "Already exists" error and cancelled. Now asks whether to open the existing catalog instead (checked against *all* catalogs, including hidden ones); choosing "Open" switches to it, otherwise the action is cancelled as before.

### Fixed

- **Arrow-key navigation jumped to the first row after renaming a file (not the first in the list) with the `F2` shortcut** — renaming triggers a disk change that `QFileSystemWatcher` picks up shortly after `refresh_and_select()`'s own refresh already ran, restarting the 400 ms debounce and firing a second, redundant `_refresh_preserve_selection()`. That method (and `refresh_and_select_paths()`) restored the previous *selection* after the table rebuild but never restored the *current index*, which the rebuild invalidates — so the renamed-to row stayed visibly selected while `currentIndex()` was `-1`, and the next arrow-key press navigated as if starting from row 0. Both methods now delegate to a new shared `_select_paths_and_set_current()` helper, which also calls `selectionModel().setCurrentIndex()` for the first restored row — centralizing the fix instead of duplicating it in both call sites.

## [1.14.0] - 2026-07-19

### Added

- **README link to the documentation** — `README.md` now links to the [Read the Docs site](https://pbpicat.readthedocs.io).

### Fixed

- `docs/conf.py`: the `## [Unreleased]` section of `CHANGELOG.md` was dropped by the RST changelog generator except for its orphaned `### Added`/`### Changed`/... subheadings, which were emitted without content and at an incorrect nesting level. `[Unreleased]` is now recognised like a dated release and included only when it has actual content.
- **Application froze (hard hang, required killing the process) after renaming a couple of files in a row with the image viewer open** — each rename made `refresh_and_select()` reload the full-size image synchronously on the GUI thread (`ImageViewer.load_image` → `load_pixmap`) while `_start_worker()` concurrently spawned `_ThumbnailWorker` background threads decoding thumbnails (`load_qimage`) for the same refreshed rows. Qt's `QImageReader`/image-format plugins are not safe to invoke concurrently from multiple threads, and decoding from the GUI thread at the same time as a worker thread deadlocked inside `QImageReader.read()`. Confirmed via a repro script that reliably hung the process, with `faulthandler` stack dumps (triggered by `SIGABRT`) pinpointing both the GUI thread and worker threads blocked in `QImageReader.read()` simultaneously. `image_io.py`'s `load_qimage()` and `load_pixmap()` now serialize all Qt decodes behind a shared `threading.Lock`.
- `FileListWidget.refresh_and_select()` did not stop the pending `_refresh_debounce` timer before refreshing, unlike its sibling refresh methods, allowing a directory-watcher-triggered refresh to fire redundantly right after a rename's explicit refresh.
- **`pbpicat.svg`** — replaced the `style="width: 100%; height: 100%;"` attribute with explicit `width="1024" height="1024"`, matching the convention used by icons in other applications.

## [1.13.0] - 2026-07-07

### Added

- **Sphinx/ReadTheDocs documentation** — `docs/` (user guide, API reference, changelog generated from `CHANGELOG.md` at build time, app icon reused as logo/favicon) and a `CODING.md` developer guide covering versioning, changelog, and release conventions. Wired into `make docs`/`make docs-live`, `.readthedocs.yaml`, and a CI job that builds the docs on every push.

## [1.12.0] - 2026-07-06

### Fixed

- **Large photos (50-100 MP phone cameras) rejected with `qt.gui.imageio: QImageIOHandler: Rejecting image as it exceeds the current allocation limit of 256 megabytes` when opened in the viewer** — Qt's default 256 MiB allocation limit is checked against the image's undecoded dimensions; a 50+ MP photo decodes to 200-400 MB as RGB32, exceeding it, which made Qt reject the read outright and fall back to a much slower full-resolution Pillow decode just to display the file. `image_io.py`'s `_make_reader()` now raises the limit to 1024 MiB (`_ALLOCATION_LIMIT_MIB`). Thumbnail generation was never affected (it downscales via `setScaledSize()`, checked against the target size, not the source).
- **Batch rotation stopped at the first failing file** — when rotating multiple selected files and one failed (e.g. a truncated JPEG), `_rotate_images()` stopped processing the rest of the selection. Now continues with the remaining files, and a single dialog lists all failures with their respective file name and message.
- **Rotation errors did not show which file caused them** — `QMessageBox` for both rotation failures and undo failures showed only the raw error text (e.g. "Premature end of JPEG file"), with no way to tell which file among the selection was at fault. Both dialogs now prefix the message with the file name.
- **Rotation on a genuinely truncated JPEG failed with the cryptic `jpegtran` message "Premature end of JPEG file"** — some files (e.g. panorama shots) are missing a small amount of data at the end, most likely from an incomplete write by the camera; `jpegtran` correctly refuses to rotate them since it cannot reconstruct the missing DCT blocks losslessly. Added a user-friendly explanation shown above the raw `jpegtran` message in `rotate_lossless()`'s `RuntimeError` (`_jpegtran_error_hints()` in `image_ops.py`).
- **Some JPEGs triggered a permanent `qt.gui.imageio.jpeg: Corrupt JPEG data: N extraneous bytes before marker 0xd9` warning** — trailing garbage bytes before the EOI marker (seen on some camera/app-produced JPEGs). Unlike the SOS defect above, there is no safe byte-level fix (the exact boundary between real entropy data and garbage can't be determined without a full Huffman decode), and it also has no practical impact: Qt/Pillow decode the image fine regardless. Silenced via `QLoggingCategory.setFilterRules("qt.gui.imageio.jpeg=false")` in `__main__.py`.
- **JPEGs from some phone cameras (e.g. certain Samsung front-camera modules) triggered a permanent `qt.gui.imageio.jpeg: Invalid SOS parameters for sequential JPEG` warning, displayed without EXIF auto-rotation, and failed lossless rotation** — these files have a malformed SOS header (`Se=0` instead of the mandatory `63` for baseline JPEGs), which `jpegtran` rejects outright and Qt's decoder merely warns about. Added `repair_jpeg_sos()` in `image_ops.py`, a lossless header fix (no entropy-coded data touched, no-op on well-formed files) applied before both Qt decoding (`image_io.py`) and `jpegtran` invocation. Also fixed `load_pixmap()`'s `auto_rotate=True` fast path, which used a bare `QPixmap(str(path))` and never actually enabled Qt's `setAutoTransform`, silently skipping EXIF auto-rotation in the main viewer (thumbnails were unaffected, as they already went through `QImageReader` with `setAutoTransform`).
- **Double-click on image opens viewer with spurious "Cannot display multiple files simultaneously" error** — Qt's `ExtendedSelection` mode emits `itemSelectionChanged` twice during a double-click (clear then re-select), causing `_on_selection_changed` to see 0 rows and wrongly trigger the multi-file message. Fixed by ignoring the transient empty-selection state (`len(rows) == 0`) in `_on_selection_changed`.
- **File list selection jumps to row 0 after opening image viewer** — `focusInEvent` called `selectRow(0)` whenever focus returned via a non-mouse event and the selection appeared empty, which happened when the viewer window stole focus. Fixed by skipping the auto-select-first-row logic while the image viewer is visible.
- **Mouse-wheel scrolling through a long file list could stall repeatedly** — restarting the visible-thumbnails worker (on each scroll-driven debounce firing) used to block the GUI thread waiting for the previous worker's current in-flight JPEG decode to finish; with large real photos and many debounce firings over a long scroll session, this added up to noticeable stalls, especially scrolling back up through thousands of rows. Restarting on scroll/resize now cancels the previous worker without blocking (`_cancel_worker_async()`), since the table itself isn't being rebuilt and a stray late thumbnail from the cancelled thread simply lands on a still-valid row.
- **Wheel/keyboard scrolling a long distance still felt slow, worse the further travelled** — unlike a scrollbar-handle drag (a single jump to a destination, loading only its final position), traversing the list with the mouse wheel passes through every intermediate row, and each pause between wheel notches longer than the debounce interval (previously 100 ms) triggered a batch load for that transient position — so the number of batches triggered, and the cumulative lag, scaled with the distance scrolled rather than the destination itself. Raised the debounce to 400 ms, comfortably longer than typical inter-notch gaps during continuous scrolling, so intermediate positions are skipped and only the position where scrolling actually settles gets loaded.
- **Rotation-error dialog could grow unusably tall with a large selection** — rotating thousands of files with many failures joined every file's error into one long plain message, pushing the OK button off-screen. The dialog now shows a short summary with the full per-file list in a collapsible/scrollable "Show Details" section (`QMessageBox.setDetailedText()`) instead.

### Added

- **Keyboard shortcuts F9 / F10** for "Apply EXIF orientation" and "Force EXIF orientation to 0°", previously accessible only via menu/toolbar. Follows the existing F6/F7/F8 rotation shortcut sequence.
- **Missing SVG icons** (`auto-rotate`, `object-rotate-left`, `object-rotate-right`, `object-flip-vertical`, `reset-exif`, `folder-new`, `folder-open`) — buttons and actions with no SVG fallback file displayed no icon on systems without an icon theme (e.g. Linux bundle).

### Changed

- **Thumbnail loading in the file list is now viewport-lazy** — previously, opening or refreshing a directory queued thumbnail generation for every file up front, in a single background thread, one at a time. On directories with thousands of files this could take many minutes, and files near the end of the list would sit without a thumbnail the whole time. `_start_worker()` now only loads thumbnails for rows currently visible (plus one screenful of margin), and re-triggers on scroll/resize (debounced) so thumbnails pop in on demand as the list is scrolled. Directory load/refresh time is no longer proportional to the total file count. Dragging the scrollbar handle across a long list skips loading until the handle is released, instead of loading a batch at every intermediate position passed through during the drag (which could add up to nearly as many decodes as loading everything).
- **Thumbnails for a freshly-scrolled-to batch of rows now load in parallel** (up to 4 concurrent `_ThumbnailWorker` threads, capped by CPU count) instead of one thread decoding the whole visible batch sequentially — cuts the delay before icons appear after landing on a new scroll position.
- **"Reset EXIF orientation" renamed to "Force EXIF orientation to 0°"** — the previous wording didn't make clear what the action actually does (menu/toolbar/shortcuts window/status tip).
- **File list column header** — now shows the number of selected files alongside the total (`File name (sel/n)`) whenever 2 or more files are selected, instead of only the total (`File name (n)`). A single selected file still shows just the total, since the count is redundant there.
- **`_linux.py` — `open_default`** now uses `subprocess.Popen(["xdg-open", …])` instead of `QDesktopServices.openUrl()`, which bypassed the user's MIME association and always opened `xed` instead of the actual default application.
- **SVG icons** — all files replaced with high-resolution (1024×1024) versions with a consistent blue rounded-square background; `pbpicat.svg` simplified (534 KB → 24 KB).
- **SVG file names** normalised: hyphens only (no underscores), semantic names (`history`, `duplicate`, `rename-template`, `reset-exif`, `auto-rotate`, `open-with`, `zoom-fit`, `zoom-in`, `zoom-out`, `zoom-original`, `zoom-width`, `zoom-height`).
- **`file_list_widget.py`** — direct `QDesktopServices.openUrl()` calls for sidecars and videos now go through `open_default()`.

### Removed

- Obsolete SVG files: `document-open-recent.svg`, `edit-copy.svg`, `template.svg`, `open_with.svg`, `zoom_fit.svg`, `zoom_in.svg`, `zoom_out.svg`, `zoom_original.svg`, `zoom_width.svg`, `zoom_height.svg`.

## [1.11.0] - 2026-06-24

### Added

- **`hooks/pyi_rth_fonts.py`** — PyInstaller runtime hook for portable
  fontconfig on Linux.  At frozen-app startup (before Qt initialises) it writes
  a minimal `fonts.conf` into `sys._MEIPASS` pointing to the bundled `fonts/`
  directory and the system `/etc/fonts/fonts.conf`, sets `FONTCONFIG_FILE`, then
  calls `FcFini()`/`FcInit()` via ctypes to force fontconfig to re-read the
  variable before `QFontDatabase` is populated.  The hook is no-op on non-Linux
  platforms and in non-frozen runs.
- **Conda fonts bundled in `pbpicat.spec`** — the `$CONDA_PREFIX/fonts/`
  directory is included as `fonts/` in the frozen bundle when it exists; the
  runtime hook above uses this directory.  `hooks/pyi_rth_fonts.py` is
  registered as a runtime hook in the spec.
- **`use_trash` setting** (default `true`) — new *Behaviour* tab in *Settings →
  Catalog configuration…* with a *Move deleted files to trash* checkbox; when
  enabled, deletions are routed through `QFile.moveToTrash()` instead of
  `Path.unlink()`.
- **`_delete_rows_and_select(next_row)`** in `FileListWidget` — removes only the
  rows corresponding to deleted files from the table without restarting the
  thumbnail worker for remaining rows; replaces the previous full-refresh call
  after deletion.
- **`fonts-conda-ecosystem`** added to `environment.yml` (Ubuntu, DejaVu,
  Inconsolata, SourceCodePro); these fonts are already bundled into the frozen
  binary via `pbpicat.spec` but were missing from the environment declaration,
  so a fresh `conda env create` would produce a bundle with no fonts.
- **`_load_bundled_fonts(app)`** in `__main__.py`: registers all bundled `.ttf`
  files into `QFontDatabase` and explicitly sets **Ubuntu** as the application
  font.  The `libfontconfig.so` bundled by PyInstaller has its default config
  path hardcoded to the build machine's conda prefix; on any other machine that
  path is absent and fontconfig fails silently, leaving Qt with no valid system
  font and an unpredictable default.  Forcing Ubuntu bypasses fontconfig for
  font selection while the runtime hook (`pyi_rth_fonts.py`) still provides a
  portable `fonts.conf` so rendering settings (anti-aliasing, hinting…) are
  inherited from the system `/etc/fonts/fonts.conf`.
- **`--dev-config-dir DIR` CLI flag** — overrides the XDG configuration directory at launch, enabling isolated test runs without touching the real config.
- **`set_base_dir()`** in `config.py` — public function to redirect `_BASE_DIR`, `_CATALOG_CONF`, and `_GLOBAL_CONFIG_PATH` before `init_catalogs()` is called.
- **`make run ARGS="..."`** — the `run` Makefile target now forwards `$(ARGS)` to the Python invocation so extra flags can be passed from the command line.
- **`argparse_qt.py`** — new module exposing `add_qt_arguments(parser)`: adds all Qt command-line flags as `--double-dash` argparse options grouped under *Qt options*; each option appends its single-dash equivalent to `args.qt_args` for direct forwarding to `QApplication`. Qt options are hidden from the `usage:` line to reduce noise while remaining fully visible in the `--help` output.
- **Ctrl+right-click zoom out** in the image viewer — symmetric with Ctrl+left-click zoom in; both center the zoom on the clicked pixel.
- **Mouse shortcuts section** in the shortcuts window — viewer mouse shortcuts (pan, center on point, zoom in/out centered on point) listed under a *Mouse* subsection alongside the existing *Keyboard* subsection.
- **`app_qsettings()`** in `config.py` — application-level `QSettings` stored in `~/.config/pbpicat/app.conf`, independent of the active catalog.
- **Persistent window geometry** — position and size of all windows (main window, image viewer, shortcuts, settings, global settings, field histories) are saved and restored between sessions; stored at application level so they survive catalog changes. The *About* dialog is excluded.
- **Qt built-in translations** — standard dialog button labels (*OK*, *Cancel*, *Close*, *Yes*, *No*, …) are now displayed in the active UI language by loading the appropriate `qtbase_<lang>.qm` file at startup.

### Changed

- **Any catalog can now be deleted** — the hard-coded protection of the `"default"` catalog is removed; the UI prevents deleting the *last* remaining catalog instead (message: *"The last catalog cannot be deleted."*). When the active catalog is deleted the app switches to the next available catalog instead of always falling back to `"default"`.
- **`load_current_catalog_name()`** — falls back to the first available catalog (instead of `"default"`) when `catalog.conf` is absent or invalid.
- **`init_catalogs()`** — no longer creates the `default` directory unconditionally; it only creates it when no catalog exists yet.
- **`fix_po_files.py`** — now also strips pybabel location comments (`#: file.py:N`) to eliminate spurious line-number churn in `.po` diffs.
- **Shortcuts window renamed** — formerly *Keyboard shortcuts*, now *Shortcuts*; made non-modal so it can stay open while working.
- **Key names localised** — *Del* and *Esc* now display as *Suppr* and *Échap* on French keyboards via `QKeySequence.toString(NativeText)`; mouse button names (*left-click*, *right-click*) are translated into each UI language.
- **Deletion confirmation dialog** — wording now adapts to the `use_trash` setting: *"Move to trash: …"* / *"Move N files to trash?"* when trash is enabled; existing *"Permanently delete"* wording otherwise.
- **Empty parent directory cleanup skipped in trash mode** — when `use_trash` is enabled the post-deletion directory sweep is omitted; the OS trash mechanism handles the directory state.

## [1.10.1] - 2026-06-14

### Fixed

- **About dialog shows wrong version in bundle** — `copy_metadata("pbpicat")` is now included in `pbpicat.spec` so that `importlib.metadata.version()` resolves correctly at runtime inside a PyInstaller bundle. `make dist` now runs `pip install -e .` beforehand to ensure package metadata matches `pyproject.toml`.

### Changed

- **`bump_version.py`** — removed the stale regex entry for `src/pbpicat/__main__.py` (no longer contains a hardcoded version string).

## [1.10.0] - 2026-06-14

### Added

- **Reset EXIF orientation** — new *Images* menu entry and ImageViewer toolbar button (*Reset EXIF orientation*) that sets the EXIF Orientation tag to 1 (normal) without rotating pixels. Disabled when the selected image has no orientation tag. Undoable (`("reset_exif", [(path, orig_orient)])`); status bar shows the count of affected files; undo restores the original tag value.
- **`exif_auto_rotate` setting** (default `true`) — new boolean config key; when false, thumbnails and the ImageViewer display images without applying the EXIF Orientation tag. Exposed in *Settings → Catalog configuration… → Images* as the "Apply EXIF rotation" checkbox. Changing the setting live reloads the current image in an open viewer via `set_auto_rotate()`.
- **F6 / F7 / F8 keyboard shortcuts** for rotation — *Rotate 90° CCW* (F6), *Rotate 180°* (F7), *Rotate 90° CW* (F8) in the main window; entries added to the keyboard shortcuts dialog.
- **X and Z as aliases in ImageViewer** — X = Fit window (alias for 0), Z = Actual size / 1:1 (alias for 1); toolbar tooltips updated to show both keys.
- **Ctrl+click in ImageViewer** — zooms to the clicked point in CUSTOM mode (previously this was done via double-click).
- **`_sanitize_exif_for_dump()`** in `image_ops.py` — converts Undefined-typed EXIF tags stored as plain integers (seen with some camera firmware) to bytes before calling `piexif.dump()`.

### Changed

- **`load_qimage` / `load_pixmap`** — added `auto_rotate` parameter (default `True`); the Pillow path now calls `ImageOps.exif_transpose()` when `auto_rotate=True`; the `QImageReader` path uses `setAutoTransform(auto_rotate)`.
- **`set_exif_orientation()`** — reads raw EXIF bytes via Pillow (`img.info["exif"]`) before calling `piexif.load()` to avoid failures on certain JPEG files; is a no-op when the file has no EXIF block; calls `_sanitize_exif_for_dump()` before `piexif.dump()`.
- **Double-click in ImageViewer** — now centers the viewport on the clicked point instead of zooming to it.
- **ImageViewer scroll centering** — on mode switch (Fit / 1:1 / Width / Height) and on image load the viewport is now centered; proportional scroll preservation is restricted to CUSTOM zoom mode.
- **`tools/fix_po_dates.py` → `tools/fix_po_files.py`** — file renamed; `make translate` updated accordingly.
- **`ruff-pre-commit`** — updated from `v0.15.15` to `v0.15.17` in `.pre-commit-config.yaml`; frozen commit hash replaced with version tag.

### Fixed

- **Zoom step additive instead of multiplicative** — zoom in/out now adds/subtracts the configured step in percentage points (e.g. 23% → 48% → 73% with a 25% step) instead of multiplying by a factor (which gave 23% → 29% → 36%).
- **`set_exif_orientation()` crash on non-standard EXIF** — `piexif.dump()` raised a type error when camera firmware had stored Undefined-typed values as integers instead of bytes; fixed by sanitizing with `_sanitize_exif_for_dump()` before dumping.

## [1.9.0] - 2026-06-13

### Added

- **Lossless rotation** — new *Images* menu entries *Rotate 90° CCW*, *Rotate 90° CW*, *Rotate 180°*, and *Apply EXIF orientation*; same buttons in the ImageViewer toolbar between zoom controls and action buttons.
  - JPEG: uses `jpegtran` (bundled in the PyInstaller executable); raises a `RuntimeError` shown as a warning dialog if unavailable.
  - Other formats (PNG, TIFF, BMP, WebP): uses Pillow — always lossless.
  - After JPEG rotation the EXIF Orientation tag is stripped via `piexif`.
  - *Apply EXIF orientation* is disabled when the selected image has no EXIF orientation tag; enabled/disabled state is kept in sync with the selection.
- **Rotation undo** — rotation operations are pushed to `_undo_stack` as `("rotation", [(path, undo_op, orig_orient)])` and undone by the existing Undo button; the button label changes to *Undo rotation (N)*.
- **`image_ops.py`** — new module: `is_jpeg`, `get_exif_orientation`, `set_exif_orientation`, `_strip_jpeg_orientation`, `_find_jpegtran`, `_jpeg_apply`, `_pil_apply`, `_pil_save_lossless`, `rotate_lossless`.
- **`piexif` dependency** — added to `pyproject.toml`, `environment.yml`, and as a PyInstaller hidden import.
- **`jpegtran` in PyInstaller bundle** — `pbpicat.spec` now locates `jpegtran` via `shutil.which` at build time and includes it as a binary; `_find_jpegtran` checks `sys._MEIPASS` first.
- **`tools/fix_po_dates.py`** — normalises `POT-Creation-Date` and `PO-Revision-Date` headers to eliminate spurious diffs between locales.
- **`tools/po_check.py`** — inspects `.po` files (statistics, untranslated entries, pattern search) without grepping or calling msgfmt (both break on multi-line entries).
- **i18n strings** — translated rotation action labels and status messages in all eight locales (de, en, es, fr, it, ru, vi, zh_CN).

### Changed

- **`make translate`** — now passes `--no-location` to `pybabel extract` (removes file/line references from `.pot`) and runs `tools/fix_po_dates.py` after `pybabel update` to keep date headers stable.
- **ImageViewer toolbar** — rotation buttons (↺ ↻ ↕ EXIF) inserted between zoom controls and action buttons; *Apply EXIF orientation* button disabled when loaded image has no orientation tag.
- **SPEC.md** — updated to document lossless rotation actions, their enabled/disabled rules, and the revised ImageViewer toolbar layout.
- **README.md** — updated to document lossless rotation, Open/Open with actions, keyboard navigation, Renumber from 1, ImageViewer keyboard shortcuts, and the Settings menu restructuring (Catalog configuration vs. Program settings).

### Fixed

- **Row selection on click after scroll** — clicking the Nth visible row (after scrolling) previously selected the Nth row from the top of the list instead of the actual clicked row. Root cause: `focusInEvent` called `selectRow(0)` before the click was processed, scrolling the viewport and shifting row coordinates. Fixed by skipping auto-select when `event.reason() == MouseFocusReason`.

## [1.8.0] - 2026-06-08

### Added

- **About dialog enriched** — now shows Python version, PySide6 version, platform string, and author(s) as clickable `mailto:` links read from package metadata.
- **Menu icons** — all menu-bar actions (File, Catalog, Images, Settings, Help) now display icons; new SVG assets created for *Quit*, *Duplicate*, *Refresh*, *Catalog configuration*, *History*, *Program settings*, *Keyboard shortcuts*, and *About*.
- **Context menu icons** — the file-list context menu reuses the same `QAction` objects as the *Images* menu, ensuring identical icons, labels, shortcuts and enabled/disabled state at all times.
- **`ui/icons.py`** — shared `get_icon(svg_name, theme_name, text_fallback)` helper that resolves icons via FreeDesktop theme → bundled SVG → text fallback; consolidates previously duplicated logic from `image_viewer.py`.
- **Keyboard shortcuts dialog** — added missing entries: Ctrl+Z (Undo rename), Ctrl+O (Open), Ctrl+Shift+O (Open with), Ctrl+N (New catalog), Ctrl+Shift+D (Duplicate catalog); Del and Escape now rendered via `QKeySequence.toString(NativeText)` for correct localisation.
- **Undo rename shortcut** — Ctrl+Z activates the *Undo rename* button.

### Changed

- **Version read from package metadata** — `importlib.metadata` replaces the hardcoded version string in `__main__.py`; the About dialog always shows the installed version.
- **Context menu selects clicked row** — right-clicking an unselected row now selects it before the menu appears, so actions operate on the expected file.

### Fixed

- **PyInstaller bundle crash on startup** — `email` was listed in `excludes` but is required by `importlib.metadata` at import time and by `email.utils` in the About dialog; removed from excludes.
- **Menu icons missing in PyInstaller bundle** — `_RESOURCE_DIR` in `ui/icons.py` was computed from `__file__`, which points inside the package directory in the bundle; now uses `sys._MEIPASS` when available, matching the actual extraction path of bundled SVG assets.

## [1.7.0] - 2026-06-08

### Added

- **Images menu** — new *Images* menu (between *Catalog* and *Settings*) with *Open* (Ctrl+O), *Open with…* (Ctrl+Shift+O), *Template*, *Delete* (Del), and *Refresh* (F5) actions.
- **Open / Open with** — *Open* launches the selected file(s) with the system default application; *Open with…* prompts for a specific application. Both actions are available in the file-list context menu and the image-viewer toolbar.
- **Platform helpers** — new `platform/` package providing XDG/Linux (application picker dialog), macOS (`open -a`), and Windows (`ShellExecuteW`) implementations for *Open with*.
- **Image viewer toolbar extended** — *Open*, *Open with*, *Template*, and *Delete* buttons added after the zoom controls.
- **Confirm deletions setting** — new catalog setting (default: on) that requires confirmation before deleting files; a configurable threshold controls whether individual file names are listed.
- **Keyboard navigation** — Left/Right arrows in the file list transfer focus to the directory tree; Right arrow on a tree leaf transfers focus back to the file list.
- **Return/Enter opens file** — pressing Return or Enter in the file list opens the image viewer (images) or the default external application (other media).
- **Auto-select on focus** — when the file list gains focus with no active selection, the first row is automatically selected.
- **New keyboard shortcuts** — Ctrl+, opens catalog settings; Ctrl+Alt+, opens program settings; both are also shown in the keyboard-shortcuts dialog.
- **Status tips on all menu actions** — every menu entry now has a descriptive status-bar tip.
- **Duplicate catalog** (Ctrl+Shift+D) — copies the current catalog's settings and field history to a new catalog name.
- **Undo rename counter** — the *Undo rename* button shows `N/total` (renames pending / total done in the session), e.g. *Undo rename 3/17*.
- **Auto-select restored files after undo** — after undoing a rename or renumber, the files moved back to their original location are automatically selected in the file list.
- **Test suite** — 551 tests across 14 modules at 98 % overall coverage; all non-UI modules and most UI modules at 100 %.

### Changed

- **"Refresh" moved to *Images* menu** — the *Refresh* action (F5) is the last entry of the *Images* menu; the now-empty *View* menu is removed.
- **Multi-selection in image viewer** — selecting more than one file while the viewer is open shows an informational message instead of closing the viewer.
- ***Catalog configuration…* renamed** — the menu entry was previously labelled *Configuration…* under *Settings*.
- **`config_dir()` moved to `platform/`** — each platform module now exposes `config_dir()` returning the OS-native configuration directory (`$XDG_CONFIG_HOME/pbpicat` on Linux, `~/Library/Application Support/pbpicat` on macOS, `%APPDATA%\pbpicat` on Windows). `config.py` no longer contains XDG-specific or OS-specific code.

### Fixed

- **Multi-selection lost after undo** — `refresh_and_select_paths` cancels the filesystem-watcher debounce before refreshing, and `_refresh_preserve_selection` now restores all previously selected rows instead of only the first.
- **Image viewer auto-updated on directory change** — the viewer no longer changes image when the file list loads a new directory or gains focus (auto-select row 0); it updates only on explicit user selection.

## [1.6.3] - 2026-06-01

### Changed

- **Build toolchain migrated to pybabel** — `xgettext`, `msgmerge`, `msgfmt`, and `msginit` replaced by `pybabel extract`, `update`, `compile`, and `init`. Removes the system `gettext` dependency; `babel` is now the sole i18n build tool.
- **Dist artifact names lowercased** — executables are now named `pbpicat-<version>-<os>-<arch>` (was `PBPicat-…`).

### Removed

- Compiled `.mo` files are no longer tracked in git; they are generated at build time.

## [1.6.2] - 2026-06-01

### Added

- **markdownlint-cli2 pre-commit hook** — Markdown files are now linted automatically on commit.

### Fixed

- **CI release asset names** — the build workflow now passes `PBPICAT_VERSION` to PyInstaller via `github.ref_name`, so release assets are correctly named `PBPicat-<version>-…` instead of `PBPicat-dev-…`.

### Changed

- Updated `SPEC.md` with v1.6.1 specifications.

## [1.6.1] - 2026-06-01

### Added

- **Keyboard shortcuts for main window menus** — `Ctrl+Q` (Quit), `Ctrl+N` (New catalog), `F5` (Refresh), `F1` (Keyboard shortcuts dialog).
- **Version in About dialog** — the application version number is now displayed in *Help → About*.
- **Image viewer toolbar and shortcuts aligned with PBPrompt** — toolbar order: Fit | 1:1 | Width | Height | + | −; bare-key shortcuts: `0` = Fit, `1` = 1:1, `W` = Width, `H` = Height, `+`/`−` = Zoom in/out.
- **SVG icons for image viewer** — zoom toolbar buttons now use the same SVG icons as PBPrompt (FreeDesktop theme → bundled SVG → text fallback).

### Changed

- `tools/git_version.sh` now uses `git status --porcelain` to detect a dirty working tree (catches untracked files in addition to modified tracked files).

## [1.6.0] - 2026-06-01

### Added

- **Delete key shortcut** — pressing `Del` in the file list deletes the selected file(s) and their sidecars; the shortcut is shown in the context menu alongside the *Delete* action.
- **Delete from image viewer** — pressing `Del` while the image viewer is open deletes the currently displayed image and its sidecars; the confirmation dialog is parented to the viewer so it stays in the foreground.
- **Keyboard shortcuts help** — new *Help → Keyboard shortcuts…* menu entry opens an HTML dialog listing all shortcuts for both the main window and the image viewer.
- **Auto-select next file after deletion** — after deleting file(s), the file immediately following the last deleted entry is automatically selected (or the last file if the deleted entry was the last one).

### Fixed

- After deleting a file, the `QFileSystemWatcher`-triggered auto-refresh (400 ms debounce) was clearing the selection; the debounced refresh now preserves the current selection by path.

## [1.5.0] - 2026-05-29

### Added

- **Delete empty sidecar files on load** — new option *Delete empty sidecar files when loading a directory* in *Configuration → Sidecar Extensions* (checked by default); zero-byte sidecar files, including orphans, are automatically deleted when entering a directory.
- **Close image viewer with Escape** — pressing Escape when the image viewer window has focus closes it.

### Fixed

- A sidecar created by double-clicking the sidecar column was immediately deleted by the empty-file cleanup triggered on refresh; newly created sidecars are now protected until the editor writes content.

## [1.4.0] - 2026-05-23

### Added

- **Directory tree context menu** — right-clicking a folder in the directory tree now shows a context menu with an *Open* action that opens the folder in the system file manager.
- **Auto-refresh on disk changes** — the file list now watches the current directory with `QFileSystemWatcher` and refreshes automatically (400 ms debounce) when files are added, removed, or renamed on disk.

### Fixed

- Directory tree scroll-to was unreliable when the widget was not yet visible at selection time; scrolling is now deferred through `showEvent` and re-triggered whenever an ancestor directory finishes loading, keeping the selected folder centred in view.

## [1.3.0] - 2026-05-17

### Added

- **Global program settings** — new *Settings → Program settings…* dialog (separated from per-catalog configuration by a menu separator) for settings that apply to the whole program rather than a single catalog.
- **Default sidecar extensions (global)** — the global settings dialog lets you define the list of sidecar extensions that new catalogs receive on creation; supports multi-dot extensions (e.g. `.prompt.txt`); includes a *Restore built-in defaults* button.
- **Language selection moved to global settings** — the interface language is now a program-level preference (stored in `global_settings.json`, independent of any catalog); requires a restart.
- **New catalog initialisation** — a newly created catalog inherits the global default sidecar extensions instead of the hard-coded built-in list.
- **Restore missing defaults — Video** — new button in *Configuration → Video* tab to non-destructively add any missing built-in video extensions.
- **Restore missing defaults — Sidecar** — new button in *Configuration → Sidecar extensions* tab to non-destructively add any missing global-default sidecar extensions.
- **Pillow / pillow-heif image support** — Pillow and pillow-heif are now runtime dependencies; formats that Qt cannot decode natively (HEIC, HEIF, AVIF, JPEG 2000, PCX, …) are loaded via a Pillow fallback in both the thumbnail worker and the image viewer.
- **Expanded default image extension list** — `DEFAULT_IMAGE_EXTENSIONS` now covers 46 formats including modern (HEIC, AVIF, JXL), RAW (Canon, Nikon, Sony, Fujifilm, …), HDR, JPEG 2000, and legacy raster formats.
- **Multi-language UI** — translation files for German, Spanish, Italian, Russian, Vietnamese, and Simplified Chinese added alongside the existing English and French.
- **`tools/bump_version.py`** — script to increment or force the project version (`major`, `minor`, `patch`, `set x.y.z`); updates `pyproject.toml`, `__main__.py`, and the EN/FR PO headers in one step. Exposed via `make bump-major / bump-minor / bump-patch / bump-set`.

### Changed

- **Settings menu layout** — *Program settings…* moved to the bottom of the *Settings* menu, separated by a divider to distinguish program-level settings from catalog-level ones (*Configuration…* and *History…*).
- **Translation headers** — PO file headers corrected: project name changed from `PBCategory` to `PBPicat`, version aligned with the project version.
- **Translation review markers** — all existing translated strings in non-English locales (DE, ES, FR, IT, RU, VI, ZH_CN) are now tagged `==AUTO==` to indicate they are pending human review.

## [1.2.0] - 2026-05-15

### Added

- **Create sidecar on double-click** — double-clicking the sidecar column of a file with no sidecar creates an empty file with the configurable default extension and opens it in the system editor.
- **Default sidecar creation extension** — new `sidecar_new_extension` setting (default `.xmp`), configurable in *Preferences → Sidecar Extensions* via a combo box populated from the active extension list.
- **Renumber from 1** — new button next to *Rename all*; renames all displayed files in-place starting from 1 according to the current schema's numeric field. Images and videos have separate counters. Supports undo via the existing *Undo last rename* button. No-ops (already correctly numbered) are detected and reported without prompting.
- **Multi-file delete** — right-clicking a selected file now deletes all selected files and their sidecars in a single confirmed operation.
- **Recursive empty directory cleanup** — after deletion, parent directories that become empty are removed recursively, matching the behaviour of rename.

### Fixed

- Sidecar column displayed only the last extension component for multi-dot extensions (e.g. `.txt` instead of `.prompt.txt`).
- Undo of renumber failed with a "files already exist" error due to circular name conflicts; undo now uses the same two-phase rename as execution.

## [1.1.0] - 2026-05-13

### Fixed

- Application icon (`pbpicat.svg`) not found when running from a PyInstaller bundle; resource path now resolves via `sys._MEIPASS` in frozen mode.

### Removed

- PNG icon generation script (`scripts/make_png.py`) and associated `make png` target; the SVG is used directly.

## [1.0.0] - 2026-05-03

Initial release.

### Features

- **Rename schema** — N configurable text fields (6 by default) that build both the destination directory tree and the filename prefix. One optional numeric counter field (`###`) auto-increments from the existing maximum, with separate counters for images and videos.
- **Sidecar support** — sidecar files (`.xmp`, `.dop`, `.pp3`, …) are renamed alongside their parent file automatically. Extensions are configurable and support multiple dots.
- **Video marker** — optional text marker inserted at a configurable position in the filename to distinguish video files from images.
- **File panel** — directory tree on the left, file list on the right with async thumbnails, sidecar indicators, and hover preview of the resulting filename.
- **Sidecar content filter** — filter the file list by a Python regex matched against sidecar file contents; only files with at least one matching sidecar are shown.
- **Context menu** — right-click a file to infer schema fields from its name (*Template*) or permanently delete it and its sidecars (*Delete*).
- **Multi-level undo** — click *Undo last rename* repeatedly to reverse successive rename operations one by one.
- **Catalog system** — named configuration profiles, each with independent settings, field histories, and window state. The `default` catalog always exists and cannot be deleted.
- **Image viewer** — double-click a thumbnail to open a zoomable viewer; it stays open and follows selection after rename or delete.
- **Internationalisation** — English and French interface; language selectable in Preferences (restart required).
- **Standalone executables** — pre-built binaries for Linux, macOS, and Windows via PyInstaller; no Python installation required.
