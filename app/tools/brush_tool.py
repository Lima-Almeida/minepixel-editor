"""
Brush Tool - Paint blocks with customizable brush size.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple
from app.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from app.ui.canvas_widget import CanvasWidget
    from app.minecraft.texturepack.models import BlockTexture


class BrushTool(BaseTool):
    """Brush tool for painting blocks with various sizes."""
    
    def __init__(self):
        super().__init__("Brush")
        self._brush_size = 1  # Size in blocks (1x1, 3x3, 5x5, etc.)
        self._last_painted_pos = None
    
    def set_brush_size(self, size: int) -> None:
        """
        Sets the brush size.
        
        Args:
            size: Brush size (must be odd: 1, 3, 5, 7, etc.)
        """
        if size < 1:
            size = 1
        # Ensure odd number for symmetry
        if size % 2 == 0:
            size += 1
        self._brush_size = size
    
    def get_brush_size(self) -> int:
        """Returns current brush size."""
        return self._brush_size
    
    def _get_brush_area(self, center_x: int, center_y: int) -> List[Tuple[int, int]]:
        """
        Gets all grid positions affected by the brush.
        
        Args:
            center_x: Center X coordinate
            center_y: Center Y coordinate
            
        Returns:
            List of (x, y) tuples
        """
        positions = []
        radius = self._brush_size // 2
        
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                positions.append((center_x + dx, center_y + dy))
        
        return positions
    
    def _paint_at(self, canvas: CanvasWidget, grid_x: int, grid_y: int) -> None:
        """
        Paints at the specified position with current brush size.
        
        Args:
            canvas: Canvas widget
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
        """
        current_block = canvas.get_current_block()
        if not current_block:
            return
        
        positions = self._get_brush_area(grid_x, grid_y)
        
        # Paint all positions in brush area
        for x, y in positions:
            if 0 <= x < canvas._grid_width and 0 <= y < canvas._grid_height:
                canvas.set_block_at(x, y, current_block, immediate_render=False)
        
        # Schedule single render for all changes
        canvas._schedule_render()
    
    def on_mouse_down(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """Paint on mouse down."""
        if button == "left":
            self._last_painted_pos = (grid_x, grid_y)
            self._paint_at(canvas, grid_x, grid_y)
    
    def on_mouse_drag(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """Paint with interpolation during drag."""
        if button == "left":
            current_block = canvas.get_current_block()
            if not current_block:
                return
            
            # Interpolate from last position to current
            if self._last_painted_pos:
                last_x, last_y = self._last_painted_pos
                
                # Get line between last and current position
                points = canvas._bresenham_line(last_x, last_y, grid_x, grid_y)
                
                # Paint at each point along the line
                for x, y in points:
                    self._paint_at(canvas, x, y)
            else:
                self._paint_at(canvas, grid_x, grid_y)
            
            self._last_painted_pos = (grid_x, grid_y)
    
    def on_mouse_up(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """Finalize painting on mouse up."""
        self._last_painted_pos = None
        # Force final render
        if canvas._dirty_blocks or canvas._pending_render:
            canvas.render(force_full=True)
    
    def get_cursor(self) -> str:
        """Returns cursor type."""
        return "crosshair"
