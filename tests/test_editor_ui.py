"""
Tests for editor behavior: hover highlight while drawing and the material list.

Runs Qt without a window (offscreen platform).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from app.core.block_manager import BlockManager  # noqa: E402
from app.core.exporter import Exporter  # noqa: E402
from app.minecraft.texturepack.models import BlockTexture  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make_block(name: str, rgb=(100, 100, 100)) -> BlockTexture:
    # The texture file doesn't exist: the canvas falls back to the average color
    return BlockTexture(block_id=f"minecraft:{name}", texture_path=Path(f"{name}.png"), avg_color=rgb)


# ---------- material list counting ----------

def test_analyze_grid_blocks_groups_variants_and_counts():
    stone, top, side = make_block("stone"), make_block("barrel_top"), make_block("barrel_side")
    grid = [
        [stone, top, side],
        [stone, top, stone],
    ]

    stats = Exporter.analyze_grid_blocks(grid, BlockManager.get_base_block_name, BlockManager.get_block_variant)

    assert stats["minecraft:stone"]["total"] == 3
    assert stats["minecraft:barrel"]["total"] == 3
    assert dict(stats["minecraft:barrel"]["variants"]) == {"top": 2, "side": 1}
    assert stats["minecraft:barrel"]["blocks"]["top"] is top


# ---------- hover highlight ----------

def send_mouse(canvas, event_type, cell, buttons):
    """Sends a mouse event at the center of a grid cell."""
    x, y = cell
    pos = QPointF(canvas.mapFromScene(QPointF(x * 16 + 8, y * 16 + 8)))
    button = Qt.MouseButton.LeftButton if event_type != QEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(event_type, pos, canvas.viewport().mapToGlobal(pos), button, buttons,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas.viewport(), event)


def test_hover_highlight_follows_cursor_while_drawing(qapp):
    from app.ui.canvas_widget import CanvasWidget

    canvas = CanvasWidget()
    canvas.resize(400, 400)
    canvas.set_grid([[make_block("stone")] * 10 for _ in range(10)])
    canvas.set_current_block(make_block("dirt", (130, 90, 60)))
    held = Qt.MouseButton.LeftButton

    send_mouse(canvas, QEvent.Type.MouseButtonPress, (1, 1), held)
    send_mouse(canvas, QEvent.Type.MouseMove, (6, 4), held)

    assert canvas._current_hover_block == (6, 4)
    assert canvas._hover_highlight_item.pos() == QPointF(6 * 16, 4 * 16)
    assert canvas.get_block_at(6, 4).block_id == "minecraft:dirt"  # still paints the line

    send_mouse(canvas, QEvent.Type.MouseButtonRelease, (6, 4), Qt.MouseButton.NoButton)
    canvas.deleteLater()


# ---------- material list refresh after painting ----------

def stats_label_texts(main_window):
    layout = main_window.stats_layout
    texts = []
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget:
            texts += [label.text() for label in widget.findChildren(QLabel)]
    return texts


def test_material_list_refreshes_after_painting(qapp):
    from app.application import MinepixelEditorApp

    editor = MinepixelEditorApp()
    editor.setup()  # loads the real block catalog and a 64x64 test grid
    canvas = editor.main_window.get_canvas()
    editor._update_block_statistics(canvas._grid)

    new_block = editor.block_manager.active_blocks[-1]
    name = BlockManager.get_base_block_name(new_block.block_id).replace("minecraft:", "")
    for x in range(10):
        canvas.set_block_at(x, 0, new_block)

    QTest.qWait(400)  # longer than the refresh delay

    expected = sum(
        1 for row in canvas._grid for b in row
        if BlockManager.get_base_block_name(b.block_id) == BlockManager.get_base_block_name(new_block.block_id)
    )
    assert f"<b>{name}:</b> {expected} blocks" in stats_label_texts(editor.main_window)
    editor.main_window.close()
