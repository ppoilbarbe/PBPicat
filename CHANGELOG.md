# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
