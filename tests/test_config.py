"""Unit tests for src/pbpicat/config.py (no real QApplication)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pbpicat.config as cfg

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_paths(tmp_path, monkeypatch):
    """Redirect all config paths to tmp_path/default (simulates the default catalog)."""
    catalog_dir = tmp_path / "default"
    catalog_dir.mkdir()
    monkeypatch.setattr(cfg, "_BASE_DIR", tmp_path)
    monkeypatch.setattr(cfg, "_CATALOG_CONF", tmp_path / "catalog.conf")
    monkeypatch.setattr(cfg, "_current_catalog", "default")
    return catalog_dir


class _FakeQSettings:
    """In-memory replacement for QSettings in tests."""

    def __init__(self, *args, **kwargs):
        self._data: dict = {}

    def value(self, key, default=None, **kwargs):
        return self._data.get(key, default)

    def setValue(self, key, value):  # noqa: N802
        self._data[key] = value

    def sync(self):
        pass

    def beginGroup(self, _g):  # noqa: N802
        pass

    def endGroup(self):  # noqa: N802
        pass

    def childKeys(self):  # noqa: N802
        return list(self._data.keys())


@pytest.fixture
def fake_qs(monkeypatch):
    qs = _FakeQSettings()
    monkeypatch.setattr(cfg, "qsettings", lambda: qs)
    return qs


# ---------------------------------------------------------------------------
# load_config / save_config
# ---------------------------------------------------------------------------


def test_load_config_no_file_returns_defaults(patched_paths):
    config = cfg.load_config()
    for k, v in cfg.DEFAULTS.items():
        assert config[k] == v


def test_load_config_merges_valid_keys(patched_paths):
    (patched_paths / "settings.json").write_text(json.dumps({"history_max": 50, "thumbnail_max_width": 256}))
    config = cfg.load_config()
    assert config["history_max"] == 50
    assert config["thumbnail_max_width"] == 256


def test_load_config_ignores_type_mismatch(patched_paths):
    (patched_paths / "settings.json").write_text(json.dumps({"history_max": "not_an_int"}))
    config = cfg.load_config()
    assert config["history_max"] == cfg.DEFAULTS["history_max"]


def test_load_config_preserves_extra_keys(patched_paths):
    (patched_paths / "settings.json").write_text(json.dumps({"last_dest": "/some/path"}))
    config = cfg.load_config()
    assert config["last_dest"] == "/some/path"


def test_load_config_invalid_json_falls_back(patched_paths):
    (patched_paths / "settings.json").write_text("not json {{{")
    config = cfg.load_config()
    for k, v in cfg.DEFAULTS.items():
        assert config[k] == v


def test_load_config_oserror_falls_back(patched_paths):
    # A directory in place of the file → open() raises IsADirectoryError (OSError)
    (patched_paths / "settings.json").mkdir()
    config = cfg.load_config()
    for k, v in cfg.DEFAULTS.items():
        assert config[k] == v


def test_save_config_creates_file(patched_paths):
    cfg.save_config({"history_max": 42})
    raw = json.loads((patched_paths / "settings.json").read_text())
    assert raw["history_max"] == 42


def test_save_load_config_roundtrip(patched_paths):
    data = {**cfg.DEFAULTS, "last_dest": "/foo/bar"}
    cfg.save_config(data)
    loaded = cfg.load_config()
    assert loaded["last_dest"] == "/foo/bar"
    assert loaded["history_max"] == cfg.DEFAULTS["history_max"]


# ---------------------------------------------------------------------------
# _load_history_file / _save_history_file
# ---------------------------------------------------------------------------


def test_load_history_file_no_file_calls_migrate(patched_paths, monkeypatch):
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {"k": ["v"]})
    assert cfg._load_history_file() == {"k": ["v"]}


def test_load_history_file_invalid_json_calls_migrate(patched_paths, monkeypatch):
    (patched_paths / "history.json").write_text("bad json")
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {})
    assert cfg._load_history_file() == {}


def test_load_history_file_oserror_calls_migrate(patched_paths, monkeypatch):
    (patched_paths / "history.json").mkdir()  # directory → OSError on open
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {"fallback": ["v"]})
    assert cfg._load_history_file() == {"fallback": ["v"]}


def test_save_and_load_history_file(patched_paths, monkeypatch):
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {})
    cfg._save_history_file({"abc": ["x", "y"]})
    assert cfg._load_history_file() == {"abc": ["x", "y"]}


# ---------------------------------------------------------------------------
# load_history / save_history / load_all_history / save_all_history
# ---------------------------------------------------------------------------


def test_load_history_missing_key(patched_paths, monkeypatch):
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {})
    assert cfg.load_history("missing") == []


def test_save_and_load_history(patched_paths, monkeypatch):
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {})
    cfg.save_history("field1", ["a", "b", "c"])
    assert cfg.load_history("field1") == ["a", "b", "c"]


def test_load_all_history(patched_paths, monkeypatch):
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {})
    cfg._save_history_file({"k1": ["v1"], "k2": ["v2"]})
    assert cfg.load_all_history() == {"k1": ["v1"], "k2": ["v2"]}


def test_save_all_history(patched_paths, monkeypatch):
    monkeypatch.setattr(cfg, "_migrate_from_qsettings", lambda: {})
    cfg.save_all_history({"k": ["x"]})
    assert cfg.load_all_history() == {"k": ["x"]}


# ---------------------------------------------------------------------------
# load_last_dest / save_last_dest
# ---------------------------------------------------------------------------


def test_load_last_dest_default(patched_paths):
    assert cfg.load_last_dest() == ""


def test_save_and_load_last_dest(patched_paths):
    cfg.save_last_dest("/my/path")
    assert cfg.load_last_dest() == "/my/path"


# ---------------------------------------------------------------------------
# load_last_source_dir / save_last_source_dir
# ---------------------------------------------------------------------------


def test_load_last_source_dir_missing_returns_home(fake_qs):
    assert cfg.load_last_source_dir() == str(Path.home())


def test_load_last_source_dir_valid(fake_qs, tmp_path):
    fake_qs._data["source/last_dir"] = str(tmp_path)
    assert cfg.load_last_source_dir() == str(tmp_path)


def test_load_last_source_dir_nonexistent_returns_home(fake_qs):
    fake_qs._data["source/last_dir"] = "/absolutely/nonexistent/path"
    assert cfg.load_last_source_dir() == str(Path.home())


def test_save_last_source_dir(fake_qs, tmp_path):
    cfg.save_last_source_dir(str(tmp_path))
    assert fake_qs._data["source/last_dir"] == str(tmp_path)


# ---------------------------------------------------------------------------
# load_video_marker_pos / save_video_marker_pos
# ---------------------------------------------------------------------------


def test_load_video_marker_pos_default(fake_qs):
    assert cfg.load_video_marker_pos() == 0


def test_save_and_load_video_marker_pos(fake_qs):
    cfg.save_video_marker_pos(3)
    assert cfg.load_video_marker_pos() == 3


# ---------------------------------------------------------------------------
# qsettings()
# ---------------------------------------------------------------------------


def test_qsettings_creates_config_dir(patched_paths):
    mock_qs = MagicMock()
    with patch("pbpicat.config.QSettings", return_value=mock_qs):
        result = cfg.qsettings()
    assert result is mock_qs
    assert patched_paths.exists()


# ---------------------------------------------------------------------------
# _migrate_from_qsettings
# ---------------------------------------------------------------------------


def test_migrate_from_qsettings_empty(monkeypatch):
    mock_qs = MagicMock()
    mock_qs.childKeys.return_value = []
    with patch("pbpicat.config.QSettings", return_value=mock_qs):
        result = cfg._migrate_from_qsettings()
    assert result == {}


def test_migrate_from_qsettings_with_data(monkeypatch):
    mock_qs = MagicMock()
    mock_qs.childKeys.return_value = ["field1"]
    mock_qs.value.return_value = ["v1", "v2"]
    with patch("pbpicat.config.QSettings", return_value=mock_qs):
        result = cfg._migrate_from_qsettings()
    assert result == {"field1": ["v1", "v2"]}


def test_migrate_from_qsettings_skips_empty_values(monkeypatch):
    mock_qs = MagicMock()
    mock_qs.childKeys.return_value = ["field1"]
    mock_qs.value.return_value = []
    with patch("pbpicat.config.QSettings", return_value=mock_qs):
        result = cfg._migrate_from_qsettings()
    assert result == {}


# ---------------------------------------------------------------------------
# Catalog management
# ---------------------------------------------------------------------------


def test_current_catalog_default(patched_paths):
    assert cfg.current_catalog() == "default"


def test_set_current_catalog(patched_paths, monkeypatch):
    (patched_paths.parent / "work").mkdir()
    cfg.set_current_catalog("work")
    assert cfg.current_catalog() == "work"
    assert (patched_paths.parent / "catalog.conf").read_text() == "work"
    monkeypatch.setattr(cfg, "_current_catalog", "default")  # restore


def test_set_current_catalog_hidden_not_persisted(patched_paths, monkeypatch):
    (patched_paths.parent / "work").mkdir()
    (patched_paths.parent / "-secret").mkdir()
    cfg.set_current_catalog("work")
    assert (patched_paths.parent / "catalog.conf").read_text() == "work"
    cfg.set_current_catalog("-secret")
    assert cfg.current_catalog() == "-secret"
    # catalog.conf still points at the last non-hidden catalog
    assert (patched_paths.parent / "catalog.conf").read_text() == "work"
    monkeypatch.setattr(cfg, "_current_catalog", "default")  # restore


def test_load_current_catalog_name_missing_file(patched_paths):
    assert cfg.load_current_catalog_name() == "default"


def test_load_current_catalog_name_valid(patched_paths):
    (patched_paths.parent / "work").mkdir()
    (patched_paths.parent / "catalog.conf").write_text("work")
    assert cfg.load_current_catalog_name() == "work"


def test_load_current_catalog_name_missing_dir(patched_paths):
    (patched_paths.parent / "catalog.conf").write_text("nonexistent")
    assert cfg.load_current_catalog_name() == "default"


def test_list_catalogs(patched_paths):
    (patched_paths.parent / "alpha").mkdir()
    (patched_paths.parent / "beta").mkdir()
    catalogs = cfg.list_catalogs()
    assert "default" in catalogs
    assert "alpha" in catalogs
    assert "beta" in catalogs
    assert catalogs == sorted(catalogs)


def test_list_catalogs_base_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_BASE_DIR", tmp_path / "nonexistent")
    assert cfg.list_catalogs() == ["default"]


def test_list_catalogs_hidden(patched_paths):
    (patched_paths.parent / "alpha").mkdir()
    (patched_paths.parent / ".hidden").mkdir()
    (patched_paths.parent / "-hidden").mkdir()
    visible = cfg.list_catalogs()
    assert "alpha" in visible
    assert ".hidden" not in visible
    assert "-hidden" not in visible
    everyone = cfg.list_catalogs(include_hidden=True)
    assert "alpha" in everyone
    assert ".hidden" in everyone
    assert "-hidden" in everyone


def test_set_base_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_BASE_DIR", cfg._BASE_DIR)
    monkeypatch.setattr(cfg, "_CATALOG_CONF", cfg._CATALOG_CONF)
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", cfg._GLOBAL_CONFIG_PATH)
    cfg.set_base_dir(tmp_path / "custom")
    assert cfg._BASE_DIR == tmp_path / "custom"
    assert cfg._CATALOG_CONF == tmp_path / "custom" / "catalog.conf"
    assert cfg._GLOBAL_CONFIG_PATH == tmp_path / "custom" / "global_settings.json"


def test_create_catalog(patched_paths):
    cfg.create_catalog("new_cat")
    assert (patched_paths.parent / "new_cat").is_dir()


def test_delete_catalog(patched_paths):
    cat_dir = patched_paths.parent / "to_delete"
    cat_dir.mkdir()
    cfg.delete_catalog("to_delete")
    assert not cat_dir.exists()


def test_delete_catalog_default_allowed(patched_paths):
    cfg.delete_catalog("default")
    assert not patched_paths.exists()


def test_init_catalogs_creates_default(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_BASE_DIR", tmp_path / "pbpicat")
    monkeypatch.setattr(cfg, "_CATALOG_CONF", tmp_path / "pbpicat" / "catalog.conf")
    cfg.init_catalogs()
    assert (tmp_path / "pbpicat" / "default").is_dir()
    assert cfg.current_catalog() == "default"
    monkeypatch.setattr(cfg, "_current_catalog", "default")


def test_init_catalogs_migrates_legacy_files(tmp_path, monkeypatch):
    base = tmp_path / "pbpicat"
    base.mkdir()
    (base / "settings.json").write_text('{"history_max": 99}')
    (base / "history.json").write_text('{"field_0": ["a"]}')
    monkeypatch.setattr(cfg, "_BASE_DIR", base)
    monkeypatch.setattr(cfg, "_CATALOG_CONF", base / "catalog.conf")
    cfg.init_catalogs()
    assert not (base / "settings.json").exists()
    assert not (base / "history.json").exists()
    assert (base / "default" / "settings.json").read_text() == '{"history_max": 99}'
    assert (base / "default" / "history.json").read_text() == '{"field_0": ["a"]}'
    monkeypatch.setattr(cfg, "_current_catalog", "default")


# ---------------------------------------------------------------------------
# load_current_catalog_name — OSError branch
# ---------------------------------------------------------------------------


def test_load_current_catalog_name_oserror(tmp_path, monkeypatch):
    """Covers the except OSError: pass branch (lines 166-167)."""
    import pathlib

    base = tmp_path / "pbpicat"
    base.mkdir()
    conf = base / "catalog.conf"
    conf.write_text("default")
    monkeypatch.setattr(cfg, "_BASE_DIR", base)
    monkeypatch.setattr(cfg, "_CATALOG_CONF", conf)

    orig_read_text = pathlib.Path.read_text

    def raise_on_conf(self, *args, **kwargs):
        if str(self) == str(conf):
            raise OSError("Permission denied")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", raise_on_conf)
    assert cfg.load_current_catalog_name() == "default"


# ---------------------------------------------------------------------------
# create_catalog — with initial_config
# ---------------------------------------------------------------------------


def test_create_catalog_with_initial_config(patched_paths):
    """Covers the initial_config branch (lines 188-191)."""
    import json

    cfg.create_catalog("new_cat", {"sidecar_extensions": [".xmp"]})
    cat_dir = patched_paths.parent / "new_cat"
    assert cat_dir.is_dir()
    data = json.loads((cat_dir / "settings.json").read_text())
    assert data["sidecar_extensions"] == [".xmp"]


def test_create_catalog_does_not_overwrite_settings(patched_paths):
    """When settings.json already exists the initial_config is ignored (line 189)."""
    import json

    cat_dir = patched_paths.parent / "existing"
    cat_dir.mkdir()
    (cat_dir / "settings.json").write_text('{"existing": true}')
    cfg.create_catalog("existing", {"new_key": False})
    data = json.loads((cat_dir / "settings.json").read_text())
    assert "existing" in data
    assert "new_key" not in data


# ---------------------------------------------------------------------------
# duplicate_catalog
# ---------------------------------------------------------------------------


def test_duplicate_catalog(patched_paths):
    """Covers lines 202-208 (normal copy of settings + history)."""
    import json

    src = patched_paths.parent / "src"
    src.mkdir()
    (src / "settings.json").write_text('{"history_max": 42}')
    (src / "history.json").write_text('{"k": ["v"]}')

    cfg.duplicate_catalog("src", "dst")

    dst = patched_paths.parent / "dst"
    assert dst.is_dir()
    assert json.loads((dst / "settings.json").read_text())["history_max"] == 42
    assert json.loads((dst / "history.json").read_text()) == {"k": ["v"]}


def test_duplicate_catalog_missing_files(patched_paths):
    """Files that do not exist in the source are not created in dest (lines 205-208)."""
    src = patched_paths.parent / "src2"
    src.mkdir()
    cfg.duplicate_catalog("src2", "dst2")
    dst = patched_paths.parent / "dst2"
    assert dst.is_dir()
    assert not (dst / "settings.json").exists()
    assert not (dst / "history.json").exists()


# ---------------------------------------------------------------------------
# load_global_config / save_global_config
# ---------------------------------------------------------------------------


def test_load_global_config_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", tmp_path / "global_settings.json")
    result = cfg.load_global_config()
    assert "default_sidecar_extensions" in result
    assert result["language"] == ""


def test_load_global_config_valid(tmp_path, monkeypatch):
    import json

    path = tmp_path / "global_settings.json"
    path.write_text(json.dumps({"language": "fr", "default_sidecar_extensions": [".xmp"]}))
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", path)
    result = cfg.load_global_config()
    assert result["language"] == "fr"
    assert result["default_sidecar_extensions"] == [".xmp"]


def test_load_global_config_type_mismatch(tmp_path, monkeypatch):
    import json

    path = tmp_path / "global_settings.json"
    path.write_text(json.dumps({"language": 123}))
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", path)
    result = cfg.load_global_config()
    assert result["language"] == ""


def test_load_global_config_invalid_json(tmp_path, monkeypatch):
    path = tmp_path / "global_settings.json"
    path.write_text("bad json {{{")
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", path)
    result = cfg.load_global_config()
    assert "default_sidecar_extensions" in result


def test_load_global_config_oserror(tmp_path, monkeypatch):
    path = tmp_path / "global_settings.json"
    path.mkdir()  # directory → OSError on open
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", path)
    result = cfg.load_global_config()
    assert "default_sidecar_extensions" in result


def test_save_global_config(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(cfg, "_BASE_DIR", tmp_path)
    path = tmp_path / "global_settings.json"
    monkeypatch.setattr(cfg, "_GLOBAL_CONFIG_PATH", path)
    cfg.save_global_config({"language": "es", "default_sidecar_extensions": [".dop"]})
    data = json.loads(path.read_text())
    assert data["language"] == "es"
    assert data["default_sidecar_extensions"] == [".dop"]


def test_init_catalogs_does_not_overwrite_existing(tmp_path, monkeypatch):
    base = tmp_path / "pbpicat"
    base.mkdir()
    default_dir = base / "default"
    default_dir.mkdir()
    (default_dir / "settings.json").write_text('{"history_max": 10}')
    (base / "settings.json").write_text('{"history_max": 99}')
    monkeypatch.setattr(cfg, "_BASE_DIR", base)
    monkeypatch.setattr(cfg, "_CATALOG_CONF", base / "catalog.conf")
    cfg.init_catalogs()
    # Existing default/settings.json preserved; legacy file removed
    assert (default_dir / "settings.json").read_text() == '{"history_max": 10}'
    assert not (base / "settings.json").exists()
    monkeypatch.setattr(cfg, "_current_catalog", "default")
