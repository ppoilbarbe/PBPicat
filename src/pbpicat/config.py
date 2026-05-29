import json
import os
import shutil
from pathlib import Path

from PySide6.QtCore import QSettings

_XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_BASE_DIR = _XDG_CONFIG_HOME / "pbpicat"
_CATALOG_CONF = _BASE_DIR / "catalog.conf"
_GLOBAL_CONFIG_PATH = _BASE_DIR / "global_settings.json"

_current_catalog: str = "default"

DEFAULT_SIDECAR_EXTENSIONS = [".xmp", ".dop", ".pp3"]

DEFAULT_VIDEO_EXTENSIONS = [
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".mts",
    ".m2ts",
    ".wmv",
    ".flv",
    ".webm",
]

DEFAULT_IMAGE_EXTENSIONS = [
    # Common raster formats
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    # Modern / recent formats
    ".heic",
    ".heif",
    ".avif",
    ".jxl",
    # RAW — generic
    ".raw",
    ".dng",
    # RAW — Canon
    ".cr2",
    ".cr3",
    # RAW — Nikon
    ".nef",
    ".nrw",
    # RAW — Sony
    ".arw",
    ".srf",
    ".sr2",
    # RAW — Olympus / OM System
    ".orf",
    # RAW — Panasonic
    ".rw2",
    # RAW — Pentax
    ".pef",
    # RAW — Fujifilm
    ".raf",
    # RAW — Hasselblad
    ".3fr",
    # RAW — Mamiya
    ".mef",
    # RAW — Minolta / Konica Minolta
    ".mrw",
    # RAW — Epson
    ".erf",
    # RAW — Kodak
    ".kdc",
    ".dcr",
    # RAW — Leica
    ".rwl",
    # RAW — Samsung
    ".srw",
    # RAW — Sigma
    ".x3f",
    # HDR / high bit-depth
    ".exr",
    ".hdr",
    # JPEG 2000
    ".jp2",
    ".j2k",
    # JPEG XR
    ".jxr",
    # Legacy raster
    ".tga",
    ".pcx",
    ".pnm",
    ".pgm",
    ".ppm",
    ".pbm",
    # Icons
    ".ico",
    # Adobe Photoshop
    ".psd",
    ".psb",
]

DEFAULTS = {
    "sidecar_extensions": DEFAULT_SIDECAR_EXTENSIONS,
    "image_extensions": DEFAULT_IMAGE_EXTENSIONS,
    "video_extensions": DEFAULT_VIDEO_EXTENSIONS,
    "video_marker": "",
    "schema_field_count": 6,
    "schema_field_titles": ["Catégorie", "Sous-cat.", "Série", "Sujet", "Détail", "Numéro"],
    "thumbnail_max_width": 128,
    "thumbnail_max_height": 128,
    "history_max": 20,
    "zoom_step_percent": 25,
    "zoom_max_percent": 400,
    "language": "",
    "sidecar_new_extension": ".xmp",
    "delete_empty_sidecars": True,
}

_DEFAULT_GLOBAL_CONFIG: dict = {
    "default_sidecar_extensions": DEFAULT_SIDECAR_EXTENSIONS,
    "language": "",
}


# ---------------------------------------------------------------------------
# Dynamic path helpers (depend on _BASE_DIR / _current_catalog at call time)
# ---------------------------------------------------------------------------


def _catalog_dir() -> Path:
    return _BASE_DIR / _current_catalog


def _config_path() -> Path:
    return _catalog_dir() / "settings.json"


def _history_path() -> Path:
    return _catalog_dir() / "history.json"


def _qsettings_path() -> Path:
    return _catalog_dir() / "ui.conf"


# ---------------------------------------------------------------------------
# Catalog management
# ---------------------------------------------------------------------------


def current_catalog() -> str:
    return _current_catalog


def load_current_catalog_name() -> str:
    """Read catalog.conf; validate that the named directory exists; fall back to 'default'."""
    if _CATALOG_CONF.exists():
        try:
            name = _CATALOG_CONF.read_text(encoding="utf-8").strip()
            if name and (_BASE_DIR / name).is_dir():
                return name
        except OSError:
            pass
    return "default"


def set_current_catalog(name: str) -> None:
    global _current_catalog
    _current_catalog = name
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    _CATALOG_CONF.write_text(name, encoding="utf-8")


def list_catalogs() -> list[str]:
    if not _BASE_DIR.exists():
        return ["default"]
    return sorted(p.name for p in _BASE_DIR.iterdir() if p.is_dir())


def create_catalog(name: str, initial_config: dict | None = None) -> None:
    catalog_dir = _BASE_DIR / name
    catalog_dir.mkdir(parents=True, exist_ok=True)
    if initial_config:
        settings_path = catalog_dir / "settings.json"
        if not settings_path.exists():
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(initial_config, f, indent=2, ensure_ascii=False)


def delete_catalog(name: str) -> None:
    if name == "default":
        raise ValueError("The default catalog cannot be deleted.")
    shutil.rmtree(_BASE_DIR / name)


def init_catalogs() -> None:
    """Ensure the default catalog exists, migrate legacy files if needed, load active catalog."""
    global _current_catalog
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    default_dir = _BASE_DIR / "default"
    default_dir.mkdir(exist_ok=True)
    # Migrate files from pre-catalog layout (directly in _BASE_DIR) into default/
    for filename in ("settings.json", "history.json", "ui.conf"):
        src = _BASE_DIR / filename
        dst = default_dir / filename
        if src.exists():
            if not dst.exists():
                src.rename(dst)
            else:
                src.unlink()
    _current_catalog = load_current_catalog_name()


# ---------------------------------------------------------------------------
# Program configuration (settings.json)
# ---------------------------------------------------------------------------


def qsettings() -> QSettings:
    """Return a QSettings instance pointing to the active catalog's ui.conf."""
    _catalog_dir().mkdir(parents=True, exist_ok=True)
    return QSettings(str(_qsettings_path()), QSettings.Format.IniFormat)


def load_config() -> dict:
    config = DEFAULTS.copy()
    path = _config_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # Only accept keys whose type matches the default; fall back to default otherwise.
            for k, default in DEFAULTS.items():
                if k in data and type(data[k]) is type(default):
                    config[k] = data[k]
            # Preserve extra keys (e.g. last_dest) that have no default.
            for k, v in data.items():
                if k not in DEFAULTS:
                    config[k] = v
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return config


def save_config(config: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_global_config() -> dict:
    config = {k: list(v) if isinstance(v, list) else v for k, v in _DEFAULT_GLOBAL_CONFIG.items()}
    if _GLOBAL_CONFIG_PATH.exists():
        try:
            with open(_GLOBAL_CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            for k, default in _DEFAULT_GLOBAL_CONFIG.items():
                if k in data and type(data[k]) is type(default):
                    config[k] = data[k]
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return config


def save_global_config(config: dict) -> None:
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# History (history.json) — one list of strings per field key
# ---------------------------------------------------------------------------


def _load_history_file() -> dict:
    path = _history_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return _migrate_from_qsettings()


def _save_history_file(data: dict) -> None:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _migrate_from_qsettings() -> dict:
    """One-time migration from legacy QSettings storage."""
    qs = QSettings("PBPicat", "PBPicat")
    data: dict = {}
    qs.beginGroup("history")
    for key in qs.childKeys():
        values = qs.value(key, [], type=list)
        if values:
            data[key] = values
    qs.endGroup()
    return data


def load_history(key: str) -> list[str]:
    return _load_history_file().get(key, [])


def save_history(key: str, values: list[str]) -> None:
    data = _load_history_file()
    data[key] = values
    _save_history_file(data)


def load_all_history() -> dict[str, list[str]]:
    return _load_history_file()


def save_all_history(data: dict[str, list[str]]) -> None:
    _save_history_file(data)


# ---------------------------------------------------------------------------
# UI state (ui.conf — QSettings IniFormat in active catalog dir)
# ---------------------------------------------------------------------------


def load_last_dest() -> str:
    return load_config().get("last_dest", "")


def save_last_dest(path: str) -> None:
    config = load_config()
    config["last_dest"] = path
    save_config(config)


def load_last_source_dir() -> str:
    """Return the last selected source directory, falling back to $HOME if missing."""
    path = qsettings().value("source/last_dir", "", type=str)
    if path and Path(path).is_dir():
        return path
    return str(Path.home())


def save_last_source_dir(path: str) -> None:
    qs = qsettings()
    qs.setValue("source/last_dir", path)
    qs.sync()


def load_video_marker_pos() -> int:
    return int(qsettings().value("schema/video_marker_pos", 0))


def save_video_marker_pos(pos: int) -> None:
    qs = qsettings()
    qs.setValue("schema/video_marker_pos", pos)
    qs.sync()
