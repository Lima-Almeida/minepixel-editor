"""
PyQt6/PySide6-based Canvas Widget for Minecraft Block Pixel Art Editor.
High-performance GPU-accelerated alternative to Dear PyGui canvas.
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict
from pathlib import Path
from PIL import Image

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from app.minecraft.texturepack.models import BlockTexture


class CanvasWidget(QGraphicsView):
    """
    High-performance PySide6 canvas widget for Minecraft block pixel art.
    
    GPU-accelerated rendering with instant pan/zoom via matrix transformations.
    """
    
    # Signals
    block_changed = Signal(int, int, object)
    selection_changed = Signal(int, int)
    
    def __init__(self, width: int = 800, height: int = 600):
        super().__init__()
        
        # Scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # Configure view
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Rendering - disable antialiasing to prevent grid artifacts at certain zoom levels
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        
        # Grid data
        self._grid: List[List[BlockTexture]] = []
        self._grid_width: int = 0
        self._grid_height: int = 0
        
        # Block rendering
        self._block_size: int = 16
        self._block_items: List[List[QGraphicsPixmapItem]] = []
        self._texture_cache: Dict[str, QPixmap] = {}
        
        # Zoom
        self._zoom_level: float = 1.0
        self._min_zoom: float = 0.1
        self._max_zoom: float = 32.0
        
        # Mouse
        self._is_panning: bool = False
        self._is_drawing: bool = False
        self._pan_start_pos: QPointF = QPointF()
        self._current_hover_block: Tuple[int, int] = (-1, -1)
        
        # Grid overlay
        self._show_grid: bool = True
        self._grid_lines: List = []
        
        # Tool
        self._current_block: Optional[BlockTexture] = None
        self._active_tool = None
        
        # Background
        self.setBackgroundBrush(QColor(45, 45, 48))
        
        # Minimum size
        self.setMinimumSize(400, 300)
        
        # Enable mouse tracking for hover
        self.setMouseTracking(True)
        
        # Line drawing
        self._last_drawn_block: Tuple[int, int] = (-1, -1)
        
        # Compatibility attributes for tools
        self._dirty_blocks: set = set()
        self._pending_render: bool = False
        
        # Hover highlight
        self._hover_highlight_item: Optional[QGraphicsPixmapItem] = None
    
    def set_grid(self, grid: List[List[BlockTexture]]) -> None:
        """Sets the block grid."""
        self.scene.clear()
        self._block_items.clear()
        self._grid_lines.clear()
        
        # Reset hover highlight
        self._hover_highlight_item = None
        self._current_hover_block = (-1, -1)
        
        if not grid or not grid[0]:
            self._grid = []
            self._grid_width = 0
            self._grid_height = 0
            return
        
        self._grid = grid
        self._grid_height = len(grid)
        self._grid_width = len(grid[0])
        
        # Create items
        self._block_items = []
        for y in range(self._grid_height):
            row = []
            for x in range(self._grid_width):
                block = grid[y][x]
                pixmap = self._get_texture(block)
                
                item = QGraphicsPixmapItem(pixmap)
                item.setPos(x * self._block_size, y * self._block_size)
                item.setTransformationMode(Qt.TransformationMode.FastTransformation)
                
                self.scene.addItem(item)
                row.append(item)
            
            self._block_items.append(row)
        
        if self._show_grid:
            self._draw_grid()
        
        self.zoom_to_fit()
    
    def get_block_at(self, x: int, y: int) -> Optional[BlockTexture]:
        """Gets block at coordinates."""
        if 0 <= y < self._grid_height and 0 <= x < self._grid_width:
            return self._grid[y][x]
        return None
    
    def set_block_at(self, x: int, y: int, block: BlockTexture, immediate_render: bool = True) -> None:
        """Sets block at coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            block: BlockTexture to set
            immediate_render: Compatibility parameter (ignored in Qt, always renders immediately)
        """
        if 0 <= y < self._grid_height and 0 <= x < self._grid_width:
            if self._grid[y][x].block_id == block.block_id:
                return
            
            self._grid[y][x] = block
            pixmap = self._get_texture(block)
            self._block_items[y][x].setPixmap(pixmap)
            
            self.block_changed.emit(x, y, block)
    
    def _get_texture(self, block: BlockTexture) -> QPixmap:
        """Loads and caches texture."""
        if block.block_id in self._texture_cache:
            return self._texture_cache[block.block_id]
        
        try:
            if block.texture_path.exists():
                pil_img = Image.open(block.texture_path).convert('RGBA')
                data = pil_img.tobytes("raw", "RGBA")
                qimage = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)
            else:
                color = block.avg_color if block.avg_color else (255, 0, 255)
                qimage = QImage(self._block_size, self._block_size, QImage.Format.Format_RGBA8888)
                qimage.fill(QColor(*color))
                pixmap = QPixmap.fromImage(qimage)
        except:
            color = block.avg_color if block.avg_color else (255, 0, 255)
            qimage = QImage(self._block_size, self._block_size, QImage.Format.Format_RGBA8888)
            qimage.fill(QColor(*color))
            pixmap = QPixmap.fromImage(qimage)
        
        self._texture_cache[block.block_id] = pixmap
        return pixmap
    
    def set_zoom(self, zoom: float) -> None:
        """Sets zoom level (GPU-accelerated)."""
        zoom = max(self._min_zoom, min(self._max_zoom, zoom))
        zoom_factor = zoom / self._zoom_level
        self._zoom_level = zoom
        self.scale(zoom_factor, zoom_factor)
    
    def zoom_in(self) -> None:
        """Zooms in."""
        if self._zoom_level < 0.5:
            factor = 1.3
        elif self._zoom_level < 1.0:
            factor = 1.25
        elif self._zoom_level < 4.0:
            factor = 1.2
        else:
            factor = 1.15
        
        self.set_zoom(self._zoom_level * factor)
    
    def zoom_out(self) -> None:
        """Zooms out."""
        if self._zoom_level < 0.5:
            factor = 0.77
        elif self._zoom_level < 1.0:
            factor = 0.8
        elif self._zoom_level < 4.0:
            factor = 0.83
        else:
            factor = 0.87
        
        self.set_zoom(self._zoom_level * factor)
    
    def zoom_to_fit(self) -> None:
        """Fits grid in view."""
        if self._grid_width == 0 or self._grid_height == 0:
            return
        
        rect = QRectF(0, 0, 
                     self._grid_width * self._block_size,
                     self._grid_height * self._block_size)
        
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        
        transform = self.transform()
        self._zoom_level = transform.m11()
    
    def reset_view(self) -> None:
        """Resets view."""
        self.resetTransform()
        self._zoom_level = 1.0
        self.centerOn(self._grid_width * self._block_size / 2,
                     self._grid_height * self._block_size / 2)
    
    def set_show_grid(self, show: bool) -> None:
        """Enables/disables grid."""
        self._show_grid = show
        
        if show:
            self._draw_grid()
        else:
            for line in self._grid_lines:
                self.scene.removeItem(line)
            self._grid_lines.clear()
    
    def _draw_grid(self) -> None:
        """Draws grid overlay."""
        for line in self._grid_lines:
            self.scene.removeItem(line)
        self._grid_lines.clear()
        
        if not self._grid:
            return
        
        pen = QPen(QColor(100, 100, 100, 128))
        pen.setWidth(0)
        
        # Vertical lines
        for x in range(self._grid_width + 1):
            line = self.scene.addLine(
                x * self._block_size, 0,
                x * self._block_size, self._grid_height * self._block_size,
                pen
            )
            self._grid_lines.append(line)
        
        # Horizontal lines
        for y in range(self._grid_height + 1):
            line = self.scene.addLine(
                0, y * self._block_size,
                self._grid_width * self._block_size, y * self._block_size,
                pen
            )
            self._grid_lines.append(line)
    
    def set_current_block(self, block: Optional[BlockTexture]) -> None:
        """Sets current block for painting."""
        self._current_block = block
    
    def get_current_block(self) -> Optional[BlockTexture]:
        """Gets current block for painting."""
        return self._current_block
    
    def set_active_tool(self, tool) -> None:
        """Sets active tool."""
        if self._active_tool:
            self._active_tool.deactivate()
        self._active_tool = tool
        if self._active_tool:
            self._active_tool.activate()
    
    def mousePressEvent(self, event):
        """Mouse press handler."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing = True
            pos = self.mapToScene(event.pos())
            grid_x = int(pos.x() / self._block_size)
            grid_y = int(pos.y() / self._block_size)
            
            if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
                self._last_drawn_block = (grid_x, grid_y)
                
                print(f"[DEBUG] Mouse click at ({grid_x}, {grid_y}), active_tool={self._active_tool}, current_block={self._current_block.block_id if self._current_block else 'None'}")
                
                if self._active_tool:
                    self._active_tool.on_mouse_down(self, grid_x, grid_y, "left")
                elif self._current_block:
                    self.set_block_at(grid_x, grid_y, self._current_block)
                else:
                    print("[WARNING] No current block or tool active!")
            
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse move handler."""
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            
            event.accept()
        elif self._is_drawing and self._current_block:
            pos = self.mapToScene(event.pos())
            grid_x = int(pos.x() / self._block_size)
            grid_y = int(pos.y() / self._block_size)
            
            if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
                if self._active_tool:
                    self._active_tool.on_mouse_drag(self, grid_x, grid_y, "left")
                else:
                    if self._last_drawn_block != (-1, -1):
                        last_x, last_y = self._last_drawn_block
                        if (grid_x, grid_y) != (last_x, last_y):
                            self._draw_line(last_x, last_y, grid_x, grid_y)
                    else:
                        self.set_block_at(grid_x, grid_y, self._current_block)
                    
                    self._last_drawn_block = (grid_x, grid_y)
            
            event.accept()
        else:
            pos = self.mapToScene(event.pos())
            grid_x = int(pos.x() / self._block_size)
            grid_y = int(pos.y() / self._block_size)
            
            if (grid_x, grid_y) != self._current_hover_block:
                self._current_hover_block = (grid_x, grid_y)
                self._update_hover_highlight(grid_x, grid_y)
                self.selection_changed.emit(grid_x, grid_y)
            
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Mouse release handler."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing = False
            self._last_drawn_block = (-1, -1)
            
            if self._active_tool:
                pos = self.mapToScene(event.pos())
                grid_x = int(pos.x() / self._block_size)
                grid_y = int(pos.y() / self._block_size)
                if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
                    self._active_tool.on_mouse_up(self, grid_x, grid_y, "left")
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event):
        """Mouse wheel for zooming."""
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        
        event.accept()
    
    def _bresenham_line(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Bresenham's line algorithm."""
        points = []
        
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        
        while True:
            points.append((x, y))
            
            if x == x1 and y == y1:
                break
            
            e2 = 2 * err
            
            if e2 > -dy:
                err -= dy
                x += sx
            
            if e2 < dx:
                err += dx
                y += sy
        
        return points
    
    def _draw_line(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Draws line of blocks."""
        if not self._current_block:
            return
        
        points = self._bresenham_line(x0, y0, x1, y1)
        for x, y in points:
            if 0 <= x < self._grid_width and 0 <= y < self._grid_height:
                self.set_block_at(x, y, self._current_block)
    
    def _update_hover_highlight(self, x: int, y: int):
        """Updates hover highlight visual feedback."""
        # Remove previous highlight
        if self._hover_highlight_item:
            self.scene.removeItem(self._hover_highlight_item)
            self._hover_highlight_item = None
        
        # Add new highlight if within bounds
        if 0 <= x < self._grid_width and 0 <= y < self._grid_height:
            # Get brush size from active tool (if it has one)
            brush_size = 1
            if self._active_tool and hasattr(self._active_tool, 'get_brush_size'):
                brush_size = self._active_tool.get_brush_size()
            
            # Calculate brush area
            radius = brush_size // 2
            highlight_width = brush_size * self._block_size
            highlight_height = brush_size * self._block_size
            
            # Create semi-transparent white overlay for entire brush area
            highlight_image = QImage(highlight_width, highlight_height, QImage.Format.Format_RGBA8888)
            highlight_image.fill(QColor(255, 255, 255, 80))  # Semi-transparent white
            
            # Center the highlight on the cursor position
            pos_x = (x - radius) * self._block_size
            pos_y = (y - radius) * self._block_size
            
            highlight_pixmap = QPixmap.fromImage(highlight_image)
            self._hover_highlight_item = QGraphicsPixmapItem(highlight_pixmap)
            self._hover_highlight_item.setPos(pos_x, pos_y)
            self._hover_highlight_item.setZValue(1000)  # On top of everything
            self.scene.addItem(self._hover_highlight_item)
    
    def get_canvas_info(self) -> dict:
        """Returns canvas info."""
        return {
            'grid_width': self._grid_width,
            'grid_height': self._grid_height,
            'zoom_level': self._zoom_level,
            'show_grid': self._show_grid,
            'block_count': self._grid_width * self._grid_height if self._grid else 0,
        }
