# PBPicat

Graphical tool for renaming image and video files along with their
sidecar files according to a structured naming schema. Built with
Python 3.12 and PySide6.

## Download

Pre-built executables for Linux, macOS and Windows are available on the
[Releases page](https://github.com/ppoilbarbe/PBPicat/releases).
Download the file matching your platform, make it executable if needed,
and run it — no installation required.

## How it works

### The rename schema

The schema is the core concept of PBPicat. It consists of N text fields
(6 by default, configurable). Each field represents one component of
the final filename and one level in the destination directory tree.

Rules:

- An empty field is skipped (no directory level, no contribution to the filename).
- A field containing only `#` characters becomes a numeric counter. The
  number of `#` sets the minimum number of digits. The counter starts
  from `max existing + 1` so files are never overwritten. Images and
  videos have separate counters.
- `_` and `.` are forbidden in any field.
- At most one numeric field is allowed per schema.

The destination directory and filename are built as follows:

- All non-empty, non-numeric fields form the directory tree under the
  root destination directory.
- The filename prefix is those same fields joined with `_`, optionally
  followed by the counter.

**Examples:**

| Schema fields | Result |
|---------------|--------|
| `Paris`, `2024`, *(empty)*, `Street`, *(empty)*, *(empty)* | `ROOT/Paris/2024/Street/Paris_2024_Street.jpg` |
| `Paris`, `2024`, *(empty)*, `Street`, *(empty)*, `###` | `ROOT/Paris/2024/Street/Paris_2024_Street_001.jpg` |
| `Paris`, `2024`, *(empty)*, `Street`, *(empty)*, `###` (existing max = 12) | `ROOT/Paris/2024/Street/Paris_2024_Street_013.jpg` |

### Sidecar files

A sidecar file shares the same stem as the image or video file, with a
different extension (e.g. `.xmp`, `.dop`, `.pp3`). PBPicat renames
sidecar files automatically alongside their parent file. Sidecar
extensions are configurable in **Settings → Preferences**.

### Video support

A configurable text marker can be inserted at a chosen position in the
filename prefix for video files. This makes it easy to distinguish
video files from images in the same directory. The marker position is
selected using radio buttons in the schema bar.

### Catalogs

A catalog is a named configuration profile. Each catalog stores its own
settings, field histories, and window state. This lets you maintain
independent schemas for different projects. Catalogs are managed from
the **Catalog** menu. The `default` catalog always exists and cannot be
deleted.

## Main window

The main window has four vertical zones:

1. **Destination** — Root directory where renamed files are placed. Use the Browse button to select it, then click **Rename All** to rename everything currently shown.

2. **Schema** — N editable fields with per-field history (combobox). Radio buttons between fields select the video marker position.

3. **File panel** — Left side: directory tree. Right side: file list showing a thumbnail, filename, and a sidecar indicator for each file.
   - Double-click a thumbnail → opens the image viewer.
   - Double-click a sidecar indicator → opens text sidecars in the system editor.
   - Right-click a file → **Template** (infer schema from the filename) or **Delete** (permanently removes the file and its sidecars).
   - Hover over a filename → shows a preview of the resulting name.

4. **Button bar** — **Undo last rename** (multi-level: click repeatedly to step back through successive rename operations), a **sidecar content filter**, and **Rename selection** (renames the currently selected files).

**Sidecar content filter** — Type a Python regular expression (case-insensitive, `.` matches newlines) into the filter box to restrict the file list to files whose sidecar content matches. Only files that have at least one matching sidecar are shown; files with no sidecar at all are hidden as soon as a filter is active. Clear the box to show all files again. Previous expressions are saved in the history so they can be reused from the dropdown.

### Renaming

Select one or more files in the list, fill in the schema fields, and
click **Rename selection** (or **Rename All** to process all visible
files). PBPicat:

- Builds the destination path and filename for each file.
- Creates any missing intermediate directories.
- Renames all sidecars alongside the main file.
- Aborts the entire operation (nothing is moved) if any destination file already exists.
- Removes empty source directories after renaming.
- Supports multi-level undo: click **Undo last rename** repeatedly to
  reverse successive rename operations one by one.

## Developer setup

### Requirements

- [conda](https://docs.conda.io/) (or any Python 3.12+ environment)
- PySide6 ≥ 6.6

### Installation

```bash
make venv      # Create the 'pbpicat' conda environment
make install   # Install the package (editable) and git hooks
```

To bypass conda (tools must be in PATH):

```bash
make install NOCONDA=1
```

### Common targets

```bash
make run       # Launch the application
make test      # Run the test suite
make coverage  # Run tests and open HTML coverage report
make lint      # Check code style (ruff)
make format    # Auto-format source code (ruff)
make help      # List all available targets
```

### Building a standalone executable

```bash
make dist
```

This produces a self-contained executable in `dist/` via PyInstaller,
named `PBPicat-<version>-<os>-<arch>`. No Python installation is
required to run it. The build bundles all translations and
dependencies.

To bump the version before building:

```bash
make bump-patch   # x.y.Z
make bump-minor   # x.Y.0
make bump-major   # X.0.0
make bump-set VERSION=1.2.3
```
