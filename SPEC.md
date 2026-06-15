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
| Images | Apply EXIF orientation | — | Apply and remove EXIF orientation tag (disabled if absent) |
| Images | Reset EXIF orientation | — | Set EXIF Orientation tag to 1 (normal) without rotating pixels (disabled if absent) |
| View | Refresh | F5 | Refresh |
| Settings | Catalog configuration… | Ctrl+, | Open catalog settings |
| Settings | History… | — | Edit field and filter history |
| Settings | Program settings… | Ctrl+Alt+, | Open program settings |
| Help | Shortcuts… | F1 | Show shortcuts window (non-modal) |
| Help | About | — | About PBPicat |

Images menu actions are disabled when no file is selected; Template is disabled with multiple selection.
Rotation actions are disabled when no image file is selected; Apply EXIF orientation and Reset EXIF orientation are additionally disabled when no selected image has an EXIF orientation tag.

All actions set `setStatusTip()` so the status bar shows the description when hovering.

**Catalog menu behaviour:**
- **New catalog…** — prompts for a name, creates the directory, switches to it.
- **Delete catalog…** — picks any existing catalog (blocked only when one catalog remains); if it is current, switches to the next available catalog first.
- Separator + dynamic list of all catalogs (checkmark on the active one) for one-click switching.

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

## Main Window (4 vertical zones)

### Zone 1 — Destination
`[Label Destination:] [QLineEdit DEST_ROOTDIR] [Btn Browse] [Btn Rename All] [Btn Renumber from 1]`

### Zone 2 — Schema
`QFrame` with N editable `QComboBox` fields interleaved with N+1 `QRadioButton` (one before, one between each field, one after).
Radio buttons (no text, with tooltip) form a `QButtonGroup`; checked button indicates video marker position (0 = before first field, N = after last).
History persisted in `history.json`. Marker position in `ui.conf` (`schema/video_marker_pos`).
`SchemaFrame` exposes `get_fields()`, `get_video_marker_pos()`, `push_history()`, `set_fields()`, `rebuild()`.

### Zone 3 — Files (FilePanel)
`QSplitter horizontal`:
- **Left**: `DirTree` — `QTreeView` with `QFileSystemModel` (directories only)
- **Right**: `FileListWidget` — QTableWidget 3 columns

#### Keyboard navigation between panels
| Location | Key | Effect |
|----------|-----|--------|
| FileListWidget | ← or → | Focus moves to DirTree |
| FileListWidget | Return / Enter | Opens current file (image viewer or external player); no effect on sidecar column |
| DirTree (leaf node) | → | Focus moves to FileListWidget; selects row 0 if nothing was selected |

A leaf node is a directory with no loaded subdirectories (`rowCount == 0` after Qt processes the key). `QFileSystemModel` loads lazily, so this also handles unscanned directories in a single keypress.

When `FileListWidget` receives focus and has no selected row, row 0 is selected automatically.

#### FileListWidget
| Col | Content | Double-click / Return | Hover |
|-----|---------|--------------|-------|
| Preview | Async thumbnail (QThread) or ▶ for video | Opens ImageViewer (images) or external player (videos) | — |
| Name | Filename | Opens ImageViewer (images) or external player (videos) | Tooltip: previewed final name (number = 1) |
| Sidecar | `●` + extensions if present, `○` otherwise | If sidecar exists: opens text sidecars (QDesktopServices). If no sidecar: opens `<stem><sidecar_new_extension>` in the default editor (file need not exist). | — |

Return/Enter acts like a double-click on the Name column (ignores the sidecar logic).

Multi-selection (ExtendedSelection).

**Auto-selection after action:**
- After renaming: selects the file that immediately followed the last renamed file in the new list (or the last file if nothing follows). ImageViewer stays open and updates.
- After deleting: selects the file that was next after the deleted one (or the last file if it was the last). ImageViewer stays open and updates.
- Startup: the restored directory is scrolled into view in the dir tree.

**Context menu (right-click on a file):**
- **Open** (Ctrl+O): opens the file with the default application via `platform.open_default`.
- **Open with…** (Ctrl+Shift+O): shows an application chooser dialog (Linux: `gio`/`.desktop` files; macOS: app name prompt; Windows: "Open as" dialog).
- **Template**: infers field values from the file stem and parent directory components, by matching against field histories. Shows a confirmation dialog; if confirmed, applies values via `SchemaFrame.set_fields()` (without pushing to history). If no match found, shows an info message.
- **Delete** (Del): permanently deletes the file and its sidecars (confirmation dialog if `confirm_deletions=true`). If the right-clicked file is among the selection, all selected files (and their sidecars) are deleted together. After deletion, empty source directories are removed recursively up the tree. Selects the next file automatically.
- **Rotate 90° CCW / CW / 180° / Apply EXIF / Reset EXIF**: rotation actions (see below).

Same actions available in the **Images** menu and in the **ImageViewer** toolbar (rotation buttons between zoom and action buttons).

**Rotation actions** (`image_ops.py`):
- JPEG lossless rotation: uses `pyjpegturbo` (turbojpeg module, optional dep). If absent, a dialog explains the requirement.
- Other formats (PNG, TIFF, BMP, WebP): uses Pillow (`rotate`, `transpose`). Always lossless for these formats.
- After JPEG rotation, the EXIF Orientation tag is stripped using `piexif` (required dep).
- All rotations and EXIF resets are **undoable**: pushed to the undo stack as `("rotation", [(path, undo_op, orig_orient)])` or `("reset_exif", [(path, orig_orient)])`. Undo button label changes accordingly.
- **Apply EXIF orientation**: reads the EXIF Orientation tag, applies the corresponding transform (rotation or flip), then strips the tag. Works for all 8 EXIF orientation values. Disabled in the UI when the image has no orientation tag.
- **Reset EXIF orientation**: sets the EXIF Orientation tag to 1 (normal) without rotating pixels. Disabled in the UI when the image has no orientation tag.

### Zone 4 — Buttons
`[Btn Undo last rename] [stretch] [ComboBox Sidecar filter] [stretch] [Btn Rename selection]`

**Sidecar filter**: editable QComboBox with history. Python regex applied to sidecar file content (re.DOTALL | re.IGNORECASE). Only files having at least one matching sidecar are shown; files with no sidecar are hidden when filter is active. History persisted in `history.json` under key `sidecar_filter`.

**Renumber from 1**: renames all displayed files in-place (same directory), assigning sequential numbers starting from 1 according to the current schema's numeric field. Images and videos have separate counters. Requires a numeric field (`#`) in the schema. Uses two-phase rename (via temp names) to avoid circular conflicts. Result enters the undo stack like a regular rename. If all files are already correctly numbered, shows a status message without prompting.

#### ImageViewer (`ui/image_viewer.py`)
Non-modal window opened by double-clicking the preview column.
Toolbar (left→right): **Fit** | **1:1** | **Width** | **Height** | sep | **+** | **−** | sep | **↺** | **↻** | **↕** | **EXIF** | **0°** | sep | **Open** | **Open with** | **Template** | **Delete** | stretch | zoom label.
The **EXIF** (Apply EXIF orientation) and **0°** (Reset EXIF orientation) buttons are disabled when the loaded image has no EXIF orientation tag.
Icons: FreeDesktop theme → `resources/zoom_*.svg` → text fallback.
Action buttons emit signals (`open_requested`, `open_with_requested`, `template_requested`, `delete_requested`) connected to `FileListWidget` handlers.
| Key | Action |
|-----|--------|
| 0 / X | Fit window (default) |
| 1 / Z | Actual size (1:1) |
| W | Fit width |
| H | Fit height |
| + / − | Zoom in / out (also numpad) |
| ↑ / ↓ | Navigate prev/next image |
| Del | Delete current image and sidecars |
| Escape | Close window |

Mouse gestures: **double-click** centers the viewport on the clicked point; **Ctrl+left-click** zooms in centered on the clicked point; **Ctrl+right-click** zooms out centered on the clicked point (both CUSTOM mode).
When switching zoom mode or loading a new image, the viewport is centered; in CUSTOM mode, scroll position is preserved proportionally.

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
- **Images**: QListWidget + add/delete for recognized image extensions; zoom step (%) and max zoom (%) for ImageViewer; "Confirm deletions" checkbox (default checked); "Apply EXIF rotation" checkbox (default checked) — controls `exif_auto_rotate`
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
- Per tab: QListWidget with internal drag-and-drop + Move Up / Move Down / Delete / Clear All buttons
- OK → `save_all_history()` then `schema_frame.rebuild(config)` to reload combos

## Persistence
| Data | File |
|------|------|
| Active catalog name | `$XDG_CONFIG_HOME/pbpicat/catalog.conf` |
| App config + `last_dest` | `$XDG_CONFIG_HOME/pbpicat/<catalog>/settings.json` |
| Field histories + sidecar filter history | `$XDG_CONFIG_HOME/pbpicat/<catalog>/history.json` |
| Last source dir (`source/last_dir`), video marker pos (`schema/video_marker_pos`) | `$XDG_CONFIG_HOME/pbpicat/<catalog>/ui.conf` (QSettings IniFormat) |
| Window geometry for all windows except About | `$XDG_CONFIG_HOME/pbpicat/app.conf` (QSettings IniFormat, via `app_qsettings()`) |
| Program-level settings (default sidecars, language) | `$XDG_CONFIG_HOME/pbpicat/global_settings.json` |

`$XDG_CONFIG_HOME` defaults to `~/.config` if unset.
`config.py` handles one-shot migration from legacy QSettings if `history.json` is absent.
`init_catalogs()` handles one-shot migration from pre-catalog flat layout (files directly in base dir → `default/`).
`--dev-config-dir DIR` CLI flag overrides `_BASE_DIR` before `init_catalogs()` via `set_base_dir()`.

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
macOS builds as `.app` bundle.
Version string: `tools/git_version.sh` locally (exact tag + clean tree → `x.y.z`, else `dev`);
CI reads `github.ref_name` and sets `PBPICAT_VERSION` before calling PyInstaller.
`make dist` runs `pip install -e .` first to ensure package metadata matches `pyproject.toml`.
Build via: `make dist`

## File Structure
```
PBPicat/
├── Makefile
├── pbpicat.spec
├── environment.yml
├── pyproject.toml
├── SPEC.md
└── src/pbpicat/
    ├── __main__.py        # CLI arg parsing (--dev-config-dir + Qt flags via argparse_qt); calls init_catalogs() then i18n.setup(app) before creating MainWindow
    ├── argparse_qt.py     # add_qt_arguments(parser): Qt flags as --double-dash options, collected in args.qt_args
    ├── config.py          # catalog mgmt + load/save config+history (JSON), qsettings() → ui.conf, app_qsettings() → app.conf
    ├── i18n.py            # gettext bootstrap
    ├── renamer.py         # pure logic (no Qt)
    ├── locale/            # en fr de es it ru vi zh_CN
    │   └── <lang>/LC_MESSAGES/pbpicat.{po,mo}
    ├── resources/
    │   ├── pbpicat.svg
    │   └── zoom_{fit,original,width,height,in,out}.svg
    ├── platform/
    │   ├── __init__.py       # dispatches to _linux / _macos / _windows at import time
    │   ├── _linux.py         # XDG: xdg-mime, gio, gtk-launch, .desktop file parsing
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
        └── image_viewer.py       # Open/OpenWith/Template/Delete signals + toolbar buttons
```
