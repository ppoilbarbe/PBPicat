# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Image viewer toolbar and shortcuts aligned with PBPrompt** — toolbar order: Fit | 1:1 | Width | Height | + | −; bare-key shortcuts: `0`=Fit, `1`=1:1, `W`=Width, `H`=Height, `+`/`−`=Zoom in/out.
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
