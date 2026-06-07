"""Tests for src/pbpicat/ui/schema_frame.py."""

import pytest
from PySide6.QtGui import QValidator

from pbpicat.config import DEFAULTS
from pbpicat.ui.schema_frame import SchemaFrame, _ForbiddenCharValidator, _SchemaField


@pytest.fixture
def config(catalog_env):
    return dict(DEFAULTS)


# ---------------------------------------------------------------------------
# _ForbiddenCharValidator
# ---------------------------------------------------------------------------


def test_validator_rejects_underscore():
    v = _ForbiddenCharValidator()
    state, text, pos = v.validate("abc_def", 3)
    assert state == QValidator.Invalid


def test_validator_rejects_dot():
    v = _ForbiddenCharValidator()
    state, text, pos = v.validate("abc.def", 3)
    assert state == QValidator.Invalid


def test_validator_accepts_clean_text():
    v = _ForbiddenCharValidator()
    state, text, pos = v.validate("abcdef", 3)
    assert state == QValidator.Acceptable


def test_validator_accepts_empty():
    v = _ForbiddenCharValidator()
    state, text, pos = v.validate("", 0)
    assert state == QValidator.Acceptable


# ---------------------------------------------------------------------------
# _SchemaField
# ---------------------------------------------------------------------------


def test_schema_field_creation(qtbot, catalog_env):
    field = _SchemaField("Category", 0, 20)
    qtbot.addWidget(field)
    assert field.value() == ""


def test_schema_field_push_history_new_value(qtbot, catalog_env):
    field = _SchemaField("Cat", 0, 20)
    qtbot.addWidget(field)
    field.push_history("Nature")
    assert field.value() == "Nature"


def test_schema_field_push_history_existing_at_top(qtbot, catalog_env):
    field = _SchemaField("Cat", 0, 20)
    qtbot.addWidget(field)
    field.push_history("A")
    field.push_history("A")
    # Already at index 0 → no duplication
    items = [field.combo.itemText(i) for i in range(field.combo.count())]
    assert items.count("A") == 1


def test_schema_field_push_history_moves_existing(qtbot, catalog_env):
    field = _SchemaField("Cat", 1, 20)
    qtbot.addWidget(field)
    field.push_history("First")
    field.push_history("Second")
    field.push_history("First")
    assert field.combo.itemText(0) == "First"


def test_schema_field_push_history_max_truncates(qtbot, catalog_env):
    field = _SchemaField("Cat", 2, 3)
    qtbot.addWidget(field)
    field.push_history("A")
    field.push_history("B")
    field.push_history("C")
    field.push_history("D")
    assert field.combo.count() <= 3


# ---------------------------------------------------------------------------
# SchemaFrame
# ---------------------------------------------------------------------------


def test_schema_frame_creation(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    assert len(frame._fields) == config["schema_field_count"]


def test_schema_frame_get_fields(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    fields = frame.get_fields()
    assert len(fields) == config["schema_field_count"]


def test_schema_frame_get_video_marker_pos_default(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    pos = frame.get_video_marker_pos()
    assert pos >= 0


def test_schema_frame_get_video_marker_pos_no_group(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    frame._marker_group = None
    assert frame.get_video_marker_pos() == 0


def test_schema_frame_set_fields(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    values = ["Alpha", "Beta", "", "Delta", "", ""]
    frame.set_fields(values)
    fields = frame.get_fields()
    assert fields[0] == "Alpha"
    assert fields[1] == "Beta"


def test_schema_frame_push_history(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    frame.push_history(["Nature", "Birds", "", "", "", ""])
    assert frame._fields[0].value() == "Nature"


def test_schema_frame_rebuild(qtbot, config):
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    new_config = dict(config)
    new_config["schema_field_count"] = 3
    new_config["schema_field_titles"] = ["A", "B", "C"]
    frame.rebuild(new_config)
    assert len(frame._fields) == 3


def test_schema_frame_marker_pos_change_saves(qtbot, config, monkeypatch):
    saved = []
    monkeypatch.setattr("pbpicat.ui.schema_frame.save_video_marker_pos", lambda pos: saved.append(pos))
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    frame._on_marker_pos_changed(2, True)
    assert saved == [2]


def test_schema_frame_marker_pos_change_unchecked_ignored(qtbot, config, monkeypatch):
    saved = []
    monkeypatch.setattr("pbpicat.ui.schema_frame.save_video_marker_pos", lambda pos: saved.append(pos))
    frame = SchemaFrame(config)
    qtbot.addWidget(frame)
    frame._on_marker_pos_changed(1, False)
    assert saved == []


def test_schema_field_with_existing_history(qtbot, catalog_env):
    """Cover the 'if history:' branch (lines 50-51) in _SchemaField.__init__."""
    from pbpicat.config import save_history

    save_history("field_3", ["Alpha", "Beta"])
    field = _SchemaField("Cat", 3, 20)
    qtbot.addWidget(field)
    items = [field.combo.itemText(i) for i in range(field.combo.count())]
    assert "Alpha" in items
