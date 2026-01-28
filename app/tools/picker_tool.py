"""
Eyedropper/Picker Tool - Pick block color from canvas.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from app.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from app.ui.canvas_widget import CanvasWidget
    from app.minecraft.texturepack.models import BlockTexture


class PickerTool(BaseTool):
    """Eyedropper tool for picking blocks from the canvas."""
    
    def __init__(self):
        super().__init__("Eyedropper")
        self._on_block_picked = None
    
    def set_on_block_picked(self, callback) -> None:
        """
        Sets callback for when a block is picked.
        
        Args:
            callback: Function(block) called when block is picked
        """
        self._on_block_picked = callback
    
    def _pick_block(self, canvas: CanvasWidget, grid_x: int, grid_y: int) -> None:
        """
        Picks the block at specified position.
        
        Args:
            canvas: Canvas widget
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
        """
        block = canvas.get_block_at(grid_x, grid_y)
        if block:
            # Set as current block
            canvas.set_current_block(block)
            
            # Notify callback
            if self._on_block_picked:
                self._on_block_picked(block)
    
    def on_mouse_down(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """Pick block on mouse down."""
        if button == "left":
            self._pick_block(canvas, grid_x, grid_y)
    
    def on_mouse_drag(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """Pick block during drag (allows continuous picking)."""
        if button == "left":
            self._pick_block(canvas, grid_x, grid_y)
    
    def on_mouse_up(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """Nothing to do on mouse up."""
        pass
    
    def get_cursor(self) -> str:
        """Returns cursor type."""
        return "hand"
