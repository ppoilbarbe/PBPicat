# Developer Guide

This document covers everything you need to contribute to PBPicat.
For user-facing information see [README.md](README.md); for a compact
functional spec see [SPEC.md](SPEC.md).

## Tech stack

| Layer       | Technology                                  |
| ----------- | ------------------------------------------- |
| Language    | Python 3.12+                                |
| GUI         | PySide6 (Qt 6 official Python binding)      |
| Linter      | ruff (line-length 120, target py312)        |
| Tests       | pytest + pytest-qt                          |
| Package mgr | conda — **conda-forge only** (`nodefaults`) |
| Build       | Hatchling (`pyproject.toml`)                |
| Packaging   | PyInstaller (`pbpicat.spec`)                |
| Docs        | Sphinx + sphinx-rtd-theme (ReadTheDocs)     |
| CI/CD       | GitHub Actions                              |

## Project layout

```text
PBPicat/
├── src/pbpicat/
│   ├── __init__.py              empty — no version/metadata duplication (see Versioning)
│   ├── __main__.py              CLI entry point; sets applicationVersion from installed metadata
│   ├── argparse_qt.py           argparse integration for Qt CLI options
│   ├── config.py                catalogs, settings persistence
│   ├── i18n.py                  gettext bootstrap
│   ├── image_io.py              Qt/Pillow image loading, thumbnailing
│   ├── image_ops.py             lossless rotation, JPEG repair helpers
│   ├── renamer.py               rename engine (schema → path)
│   ├── platform/                OS-specific abstractions (_linux/_macos/_windows)
│   ├── resources/                bundled resource files (SVG icons, …)
│   └── ui/                      main window, dialogs, custom widgets
├── tests/                       one test file per module, `test_ui_*` for widgets
├── tools/
│   ├── bump_version.py          bumps/sets the version in pyproject.toml
│   ├── changelog_notes.py       reads CHANGELOG.md entry for a version (CI release)
│   ├── git_version.sh           version-at-build-time: tag if clean+tagged, else "dev"
│   ├── fix_po_files.py          post-processes .po files after pybabel update
│   └── po_check.py              inspect .po files (stats, untranslated, search) — use instead of grep/msgfmt
├── docs/                        Sphinx documentation source (see Documentation)
│   ├── conf.py                   Sphinx config — reads version, converts CHANGELOG.md → changelog.rst
│   ├── index.rst                 landing page + toctree
│   ├── user_guide.rst             user-facing manual
│   ├── api.rst                   autodoc directives, one section per module
│   └── requirements.txt          pinned docs dependencies (mirrors [dev] extras subset, for RTD)
├── .github/workflows/ci.yml     CI pipeline
├── .readthedocs.yaml            ReadTheDocs build configuration
├── pbpicat.spec                 PyInstaller build spec
├── environment.yml              conda environment declaration
├── pyproject.toml               project metadata + tool configuration — sole source of the version
├── Makefile                     development task runner
├── SPEC.md                      compact functional spec (kept up to date on every significant change)
└── CHANGELOG.md                 Keep a Changelog — Added/Changed/Deprecated/Removed/Fixed/Security
```

## Setup

```bash
make venv            # create the 'pbpicat' conda environment
conda activate pbpicat
make install          # pip install -e ".[dev]"  +  pre-commit install
```

### Running without conda

Set `NOCONDA` to bypass conda wrapping; every tool must then be on `PATH`:

```bash
make test NOCONDA=1
export NOCONDA=1 && make lint test
```

`make venv` and `make venv-update` always invoke `conda` directly and are
unaffected by `NOCONDA`.

## Daily workflow

Run `make` (or `make help`) to list all targets. Key ones:

| Task                     | Command                                         |
| ------------------------ | ----------------------------------------------- |
| Run the application      | `make run`                                      |
| Run tests                | `make test`                                     |
| HTML coverage report     | `make coverage`                                 |
| Lint & style check       | `make lint`                                     |
| Auto-format              | `make format`                                   |
| Run all pre-commit hooks | `make hooks`                                    |
| Update translations      | `make translate`                                |
| Build standalone binary  | `make dist`                                     |
| Build source archive     | `make srcdist`                                  |
| Build docs               | `make docs`                                     |
| Live-reload docs         | `make docs-live`                                |
| Remove build artifacts   | `make clean`                                    |
| Bump patch/minor/major   | `make bump-patch` / `bump-minor` / `bump-major` |
| Force a specific version | `make bump-set VERSION=x.y.z`                   |

## Coding conventions

- **Language**: English — all identifiers, comments, docstrings, and commit
  messages must be in English (project is in `full-en` mode; see `CLAUDE.md`).
- **Style**: enforced by `ruff` (line length 120, target Python 3.12).
- **Comments**: only when the *why* is non-obvious. No narration of what the
  code obviously does; no multi-line comment blocks.
- **No gold-plating**: implement only what the task requires; no speculative
  abstractions or backward-compatibility shims.
- Sidecar paths are always built as `parent / (stem + ext)`, never
  `Path.with_suffix()` — sidecar extensions can contain multiple dots.

## Versioning

PBPicat keeps a **single source of truth** for the version: the `version`
field in `pyproject.toml`. There is no duplicate constant in
`src/pbpicat/__init__.py` — that file is intentionally empty.

| Context                                                                        | How the version is obtained                                                                                                                                                                                                                                                         |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Running from an editable/installed package (`make run`, tests, `About` dialog) | `importlib.metadata.version("pbpicat")`, read from the installed distribution's metadata (ultimately sourced from `pyproject.toml`)                                                                                                                                                 |
| `__main__.py`                                                                  | `app.setApplicationVersion(version("pbpicat"))` at startup; the UI reads it back via `QCoreApplication.applicationVersion()`                                                                                                                                                        |
| PyInstaller build (`make dist` / CI `build` job)                               | `tools/git_version.sh` — the exact Git tag (e.g. `v1.2.3` → `1.2.3`) when `HEAD` is tagged **and** the working tree is clean, else `"dev"`. Passed to `pbpicat.spec` via the `PBPICAT_VERSION` env var and baked into the artifact name and (on macOS) `CFBundleShortVersionString` |

Bumping the version updates `pyproject.toml` only:

```bash
make bump-patch                  # 1.2.3 → 1.2.4
make bump-minor                  # 1.2.3 → 1.3.0
make bump-major                  # 1.2.3 → 2.0.0
make bump-set VERSION=1.5.0      # jump to an arbitrary version (must be > current)
```

`tools/bump_version.py` is intentionally a single-file patcher (`_FILES` list
of one entry) — if a second version-bearing file is ever introduced, add it
there rather than hand-editing multiple places.

## CHANGELOG

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/). Every user-visible change
gets an entry under `## [Unreleased]`, grouped under `### Added` /
`Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`, written in
English regardless of the project's language mode.

`tools/changelog_notes.py` extracts the body of a single `## [x.y.z]`
section by version number — used by CI to populate the GitHub release
description, and usable locally:

```bash
python tools/changelog_notes.py 1.12.0
```

## Documentation (Sphinx / ReadTheDocs)

`docs/` holds the Sphinx source published to ReadTheDocs. Build it locally
with `make docs` (output in `docs/_build/html/index.html`) or
`make docs-live` for hot-reload while editing.

- **Version** (`docs/conf.py`) — same single source of truth as everywhere
  else: `release = importlib.metadata.version("pbpicat")`. This requires
  the package to be installed (`pip install -e .`, done by `make install`
  and by ReadTheDocs' build via `.readthedocs.yaml`); it is *not* read from
  `pyproject.toml` directly, to stay consistent with how the running
  application resolves its own version (see Versioning above).
- **Changelog** (`docs/changelog.rst`) — generated at build time from
  `CHANGELOG.md` by a converter function in `conf.py` (Markdown `##`/`###`
  headings → RST sections, inline code/bold → RST equivalents). The
  generated file is gitignored; never hand-edit it — edit `CHANGELOG.md`.
- **API reference** (`docs/api.rst`) — one `automodule` block per source
  module. `PySide6` is mocked (`autodoc_mock_imports`) so autodoc can import
  modules without a display; any module with a PySide6 type in a bare
  (non-deferred) annotation combined with `|` (e.g. `QBuffer | None`) must
  add `from __future__ import annotations` at the top, otherwise the mocked
  type's `__or__` raises `TypeError` at import time and autodoc fails.
- **User guide** (`docs/user_guide.rst`) — hand-written manual; keep it in
  sync with `README.md`'s feature descriptions when either changes.

`.readthedocs.yaml` builds on Ubuntu with Python 3.12, installs the package
with the `dev` extra (which includes `sphinx`, `sphinx-rtd-theme`,
`sphinx-autobuild`), and runs `sphinx-build` per `docs/conf.py`.

## Releasing

1. Add entries to `CHANGELOG.md` under `## [Unreleased]` as changes land.
2. When ready to release, bump the version and turn `[Unreleased]` into a
   dated section:

   ```bash
   make bump-patch                  # or bump-minor / bump-major / bump-set
   ```

   Then edit `CHANGELOG.md`: rename `## [Unreleased]` to
   `## [x.y.z] - YYYY-MM-DD` and add a fresh empty `## [Unreleased]` above it.
3. Commit: `git add -p && git commit -m "chore: release vX.Y.Z"`.
4. Tag and push: `git tag vX.Y.Z && git push --tags`.

The CI pipeline (`.github/workflows/ci.yml`) takes over from there:

```text
push / PR
  ├── test   (ubuntu) ──┐
  └── hooks  (ubuntu) ──┴── build ──── release  ← semver tags only
                              ├── ubuntu
                              ├── windows
                              └── macos
```

- `build` calls PyInstaller directly (not `make dist`), with
  `PBPICAT_VERSION` set from the tag name (stripped of `v`) so the artifact
  name matches the release, e.g. `pbpicat-1.12.0-linux-x86_64`.
- `release` (tags matching `v[0-9]*.[0-9]*.[0-9]*` only) downloads all
  platform artifacts, extracts the matching `CHANGELOG.md` section via
  `tools/changelog_notes.py`, and creates a GitHub release with that text as
  body and the three binaries attached.

## Internationalisation (i18n)

Translatable strings are wrapped with `_()`. The toolchain:

```text
Python source
       │
       ▼ pybabel extract
  locale/pbpicat.pot            ← template (not committed)
       │
       ▼ pybabel update / pybabel init
  locale/<lang>/LC_MESSAGES/pbpicat.po   ← human-edited, committed
       │
       ▼ pybabel compile
  locale/<lang>/LC_MESSAGES/pbpicat.mo   ← binary catalogue, committed
```

Run `make translate` to regenerate everything for all languages listed in
`PO_LOCALES` (Makefile). To inspect `.po` files (statistics, untranslated
entries, pattern search) use `tools/po_check.py` — never `grep` or `msgfmt`,
both break on multi-line entries.

Every time a user-visible string is added, removed, or modified, update the
translations (`make translate`) as part of the same change.

## Testing

```bash
make test               # full suite — terminal coverage report
make coverage            # full suite + HTML report in htmlcov/index.html
pytest -k test_foo       # run a single test by name
```

Tests live in `tests/`, one file per source module (`test_ui_*.py` for
widgets). Use `qtbot` from `pytest-qt` for all widget interactions; never
instantiate `QApplication` manually.

## Packaging (`make dist`)

`make dist` runs `translate` then calls PyInstaller with `pbpicat.spec`,
using the version from `tools/git_version.sh`.

| Platform | Output                                  |
| -------- | --------------------------------------- |
| Linux    | `dist/pbpicat-<ver>-linux-x86_64`       |
| Windows  | `dist/pbpicat-<ver>-windows-x86_64.exe` |
| macOS    | `dist/pbpicat-<ver>-macos-arm64.app`    |

`make srcdist` builds a matching source archive via `git archive`:
`dist/pbpicat-<ver>-src.tar.gz`. Both targets use the same version string
from `tools/git_version.sh`.

PyInstaller cannot cross-compile; each platform must build natively.

## License

GPLv3 — all contributions must be compatible with this license.
