"""Tests for src/pbpicat/ui/file_panel.py."""

import pytest

from pbpicat.config import DEFAULTS
from pbpicat.ui.file_panel import FilePanel


@pytest.fixture
def config(catalog_env):
    c = dict(DEFAULTS)
    c["confirm_deletions"] = False
    c["delete_empty_sidecars"] = False
    return c


def test_file_panel_creation(qtbot, config):
    panel = FilePanel(config)
    qtbot.addWidget(panel)
    assert panel.file_list is not None
    assert panel.dir_tree is not None


def test_file_panel_refresh(qtbot, config):
    panel = FilePanel(config)
    qtbot.addWidget(panel)
    panel.refresh()  # no crash when no directory loaded


def test_file_panel_reconfigure(qtbot, config):
    panel = FilePanel(config)
    qtbot.addWidget(panel)
    new_config = dict(config)
    new_config["thumbnail_max_width"] = 64
    panel.reconfigure(new_config)
    assert panel.file_list._thumb_w == 64
