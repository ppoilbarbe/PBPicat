User Guide
==========

.. contents:: On this page
   :local:
   :depth: 2

Installation
------------

PBPicat is distributed as a standalone executable. Download the file for
your platform from the `GitHub Releases
<https://github.com/ppoilbarbe/PBPicat/releases>`_ page, make it executable
if needed, and run it directly — no Python installation required.

Launching
---------

Run the binary (or ``python -m pbpicat`` from a development environment).

The rename schema
------------------

The schema is the core concept of PBPicat. It consists of *N* text fields
(6 by default, configurable). Each field represents one component of the
final filename and one level in the destination directory tree.

Rules:

* An empty field is skipped (no directory level, no contribution to the
  filename).
* A field containing only ``#`` characters becomes a numeric counter. The
  number of ``#`` sets the minimum number of digits. The counter starts
  from ``max existing + 1`` so files are never overwritten. Images and
  videos have separate counters.
* ``_`` and ``.`` are forbidden in any field.
* At most one numeric field is allowed per schema.

The destination directory and filename are built as follows:

* All non-empty, non-numeric fields form the directory tree under the root
  destination directory.
* The filename prefix is those same fields joined with ``_``, optionally
  followed by the counter.

.. list-table:: Examples
   :header-rows: 1
   :widths: 45 55

   * - Schema fields
     - Result
   * - ``Paris``, ``2024``, *(empty)*, ``Street``, *(empty)*, *(empty)*
     - ``ROOT/Paris/2024/Street/Paris_2024_Street.jpg``
   * - ``Paris``, ``2024``, *(empty)*, ``Street``, *(empty)*, ``###``
     - ``ROOT/Paris/2024/Street/Paris_2024_Street_001.jpg``
   * - Same, with an existing max of 12
     - ``ROOT/Paris/2024/Street/Paris_2024_Street_013.jpg``

Sidecar files
-------------

A sidecar file shares the same stem as the image or video file, with a
different extension (e.g. ``.xmp``, ``.dop``, ``.pp3``). PBPicat renames
sidecar files automatically alongside their parent file. Sidecar
extensions are configurable in **Settings → Catalog configuration**.

Video support
-------------

A configurable text marker can be inserted at a chosen position in the
filename prefix for video files. This makes it easy to distinguish video
files from images in the same directory. The marker position is selected
using radio buttons in the schema bar.

Catalogs
--------

A catalog is a named configuration profile. Each catalog stores its own
settings, field histories, and window state. This lets you maintain
independent schemas for different projects. Catalogs are managed from the
**Catalog** menu. The ``default`` catalog always exists and cannot be
deleted.

The main window
----------------

The main window has four vertical zones:

1. **Destination** — root directory where renamed files are placed. Use
   the Browse button to select it, then click **Rename All** to rename
   everything currently shown.
2. **Schema** — *N* editable fields with per-field history (combobox).
   Radio buttons between fields select the video marker position.
3. **File panel** — left side: directory tree; right side: file list
   showing a thumbnail, filename, and a sidecar indicator for each file.

   * Double-click a thumbnail or filename opens the image viewer (images)
     or the system player (videos).
   * Double-click a sidecar indicator opens the sidecar in the system
     editor; if several sidecars exist, a small menu lets you pick which
     one to open; if no sidecar exists, one is created.
   * Right-click a file opens a context menu (same actions as the
     **Images** menu, see below).
   * Hovering over a filename shows a preview of the resulting name.
   * Keyboard navigation: Tab (and Shift+Tab) toggles focus between the
     directory tree and the file list. In the tree, the four arrow keys
     navigate directories only. In the file list, Up/Down move the
     selection. In both panels, Home/End jump to the first/last entry.
     Return/Enter opens the selected file.
4. **Button bar** — **Undo last rename** (Ctrl+Z, multi-level, shows
   N/total pending), a sidecar content filter, **Rename selection**, and
   **Renumber from 1**.

**Sidecar content filter** — type a Python regular expression
(case-insensitive, ``.`` matches newlines) into the filter box to restrict
the file list to files whose sidecar content matches. Only files with at
least one matching sidecar are shown; files with no sidecar at all are
hidden as soon as a filter is active. Clear the box to show all files
again. Previous expressions are saved in the history.

**Renumber from 1** — renames all displayed files in-place, assigning
sequential numbers starting from 1 according to the numeric field (``#``)
in the current schema. Images and videos are numbered separately. The
result is undoable.

Images menu
~~~~~~~~~~~

The **Images** menu (and the file-list context menu) provides:

``Open`` (Ctrl+O)
    Open the selected file(s) with the system default application.

``Open with…`` (Ctrl+Shift+O)
    Choose a specific application to open the file.

``Template``
    Infer field values from the selected filename; shows a confirmation
    dialog before applying.

``Delete`` (Del)
    Permanently delete the selected file(s) and their sidecars. A
    confirmation dialog is shown by default. Empty source directories are
    removed after deletion.

``Rotate 90° CCW`` (F6) / ``Rotate 90° CW`` (F8) / ``Rotate 180°`` (F7)
    Lossless rotation (JPEG via ``jpegtran``; PNG/TIFF/BMP/WebP via
    Pillow). Rotation is undoable.

``Apply EXIF orientation`` (F9)
    Apply the EXIF orientation tag as a physical transform and strip the
    tag. Disabled when no EXIF orientation is present.

``Reset EXIF orientation`` (F10)
    Set the EXIF Orientation tag to 1 (normal) without rotating pixels.
    Disabled when no EXIF orientation is present. Undoable.

``Refresh`` (F5)
    Reload the current directory.

Renaming
~~~~~~~~

Select one or more files in the list, fill in the schema fields, and click
**Rename selection** (or **Rename All** to process all visible files).
PBPicat:

* Builds the destination path and filename for each file.
* Creates any missing intermediate directories.
* Renames all sidecars alongside the main file.
* Aborts the entire operation (nothing is moved) if any destination file
  already exists.
* Removes empty source directories after renaming.
* Supports multi-level undo: click **Undo last rename** (or press Ctrl+Z)
  repeatedly to reverse successive rename and renumber operations one by
  one.

The image viewer
~~~~~~~~~~~~~~~~~

Double-clicking a thumbnail opens the non-modal image viewer. Its toolbar
provides zoom controls (**Fit**, **1:1**, **Width**, **Height**, **+**,
**−**), rotation buttons (**↺**, **↻**, **↕**, **EXIF**, **0°**), and file
action buttons (**Open**, **Open with**, **Template**, **Delete**).

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Action
   * - 0 / X
     - Fit window
   * - 1 / Z
     - Actual size (1:1)
   * - W
     - Fit width
   * - H
     - Fit height
   * - \+ / −
     - Zoom in / out
   * - ↑ / ↓
     - Navigate previous/next image
   * - Del
     - Delete current image and sidecars
   * - Escape
     - Close window

Double-click on the image centers the viewport on the clicked point.
Ctrl+click zooms to the clicked point.

Settings
--------

``Settings → Catalog configuration…`` (Ctrl+,)
    Per-catalog settings: rename schema (field count, titles, max
    history), sidecar extensions, image extensions, video extensions and
    marker, thumbnail size, zoom, deletion confirmation, and EXIF
    auto-rotation.

``Settings → Program settings…`` (Ctrl+Alt+,)
    Application-wide settings: default sidecar extensions for new
    catalogs and interface language (restart required).

``Settings → Histories…``
    Edit, reorder, or clear the field and filter histories.

``Help → Keyboard shortcuts…`` (F1)
    Full list of keyboard shortcuts.
