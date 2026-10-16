"""
Tests for BlockManager filtering rules and for the SettingsDialog that edits them.

Uses a small synthetic texture folder, so the tests don't depend on the real assets.
"""

from __future__ import annotations

import os

import pytest
from PIL import Image

from app.core.block_manager import BlockManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def write_texture(folder, name: str, rgba) -> None:
    Image.new("RGBA", (16, 16), rgba).save(folder / f"{name}.png")


@pytest.fixture
def manager(tmp_path):
    """
    Synthetic texture pack:
    - stone, dirt: solid and allowed
    - bedrock: listed in the ignored file by its own name
    - barrel_top + barrel_side: only one variant is listed -> the whole barrel is ignored
    - glass: fully transparent
    """
    write_texture(tmp_path, "stone", (120, 120, 120, 255))
    write_texture(tmp_path, "dirt", (130, 90, 60, 255))
    write_texture(tmp_path, "bedrock", (40, 40, 40, 255))
    write_texture(tmp_path, "barrel_top", (150, 110, 70, 255))
    write_texture(tmp_path, "barrel_side", (140, 100, 60, 255))
    write_texture(tmp_path, "glass", (200, 230, 255, 0))

    bm = BlockManager(tmp_path)
    bm.default_ignored_blocks = {"bedrock", "barrel_top"}  # names as in ignored_textures.txt
    bm.load_blocks()
    return bm


EXPECTED_DEFAULT = {"minecraft:bedrock", "minecraft:barrel", "minecraft:glass"}


# ---------- BlockManager ----------

def test_default_ignored_bases_applies_all_rules(manager):
    assert manager.default_ignored_bases() == EXPECTED_DEFAULT


def test_load_starts_with_the_default_ignored_bases(manager):
    assert manager.user_ignored_blocks == EXPECTED_DEFAULT
    assert {b.block_id for b in manager.matcher.blocks} == {"minecraft:stone", "minecraft:dirt"}


def test_default_ignored_bases_does_not_change_state(manager):
    manager.set_ignored_blocks({"minecraft:stone"})

    manager.default_ignored_bases()

    assert manager.user_ignored_blocks == {"minecraft:stone"}


def test_set_ignored_blocks_updates_active_blocks_and_matcher(manager):
    manager.set_ignored_blocks({"minecraft:stone"})

    active_ids = {b.block_id for b in manager.active_blocks}
    assert "minecraft:stone" not in active_ids
    assert "minecraft:bedrock" in active_ids
    assert "minecraft:stone" not in {b.block_id for b in manager.matcher.blocks}


def test_ignoring_every_block_leaves_no_matcher(manager):
    every_base = {BlockManager.get_base_block_name(b.block_id) for b in manager.all_blocks}

    manager.set_ignored_blocks(every_base)

    assert manager.active_blocks == []
    assert manager.matcher is None


def test_reset_to_defaults(manager):
    manager.set_ignored_blocks(set())

    manager.reset_to_defaults()

    assert manager.user_ignored_blocks == EXPECTED_DEFAULT


# ---------- SettingsDialog ----------

@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp, manager, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.ui.dialogs.settings_dialog import SettingsDialog

    # Answer "Yes" to confirmations (reset) and "No" to the re-render question
    def answer(parent, title, *args, **kwargs):
        return QMessageBox.StandardButton.Yes if title == "Reset to Default" else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(answer))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    d = SettingsDialog(manager)
    yield d
    d.deleteLater()


def test_dialog_reset_matches_block_manager_defaults(dialog, manager):
    dialog._activate_all()

    dialog._reset_to_default()

    assert dialog._ignored_bases_on_screen() == manager.default_ignored_bases()


def test_dialog_reset_then_cancel_keeps_block_manager_unchanged(dialog, manager):
    manager.set_ignored_blocks({"minecraft:stone"})
    dialog._populate_lists(manager.user_ignored_blocks)

    dialog._reset_to_default()
    dialog.reject()

    assert manager.user_ignored_blocks == {"minecraft:stone"}


def test_dialog_save_applies_lists_to_block_manager(dialog, manager):
    dialog._activate_all()

    dialog._save_and_apply()

    assert manager.user_ignored_blocks == set()
    # Every solid texture is now matched; glass stays out because the matcher skips transparency
    assert {b.block_id for b in manager.matcher.blocks} == {
        "minecraft:stone", "minecraft:dirt", "minecraft:bedrock",
        "minecraft:barrel_top", "minecraft:barrel_side",
    }


def test_dialog_refuses_to_save_without_active_blocks(dialog, manager):
    before = set(manager.user_ignored_blocks)
    dialog._ignore_all()

    dialog._save_and_apply()

    assert manager.user_ignored_blocks == before
    assert manager.matcher is not None
