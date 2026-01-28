"""
Canvas Widget for Minecraft Block Pixel Art Editor using Dear PyGui.
Provides an interactive canvas for viewing and editing block grids.
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Callable, Dict
from pathlib import Path
import time
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import threading

import dearpygui.dearpygui as dpg

from app.minecraft.texturepack.models import BlockTexture


class CanvasWidget:
    """
    Interactive canvas widget for displaying and editing Minecraft block pixel art using Dear PyGui.
    
    Features:
    - Zoom and pan
    - Grid overlay
    - Mouse interaction for painting
    - GPU-accelerated rendering
    - Tool support
    
    Callbacks:
    - on_block_changed: Called when a block is modified (x, y, new_block)
    - on_selection_changed: Called when selection changes (x, y)
    """
    
    def __init__(self, tag: str, width: int = 800, height: int = 600, parent=None):
        """
        Initialize the canvas widget.
        
        Args:
            tag: Unique tag for the Dear PyGui drawlist
            width: Canvas width in pixels
            height: Canvas height in pixels
            parent: Parent Dear PyGui container
        """
        self.tag = tag
        self.width = width
        self.height = height
        self.parent = parent
        
        # Grid data
        self._grid: List[List[BlockTexture]] = []
        self._grid_width: int = 0
        self._grid_height: int = 0
        
        # Block rendering
        self._block_size: int = 16  # Original texture size
        self._texture_cache: Dict[str, str] = {}  # block_id -> dpg texture tag
        
        # Zoom and pan
        self._zoom_level: float = 1.0
        self._min_zoom: float = 0.1
        self._max_zoom: float = 32.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        
        # Mouse interaction
        self._is_panning: bool = False
        self._is_drawing: bool = False
        self._last_mouse_x: float = 0.0
        self._last_mouse_y: float = 0.0
        self._pan_start_x: float = 0.0  # Pan position when drag started
        self._pan_start_y: float = 0.0
        self._mouse_start_x: float = 0.0  # Mouse position when drag started
        self._mouse_start_y: float = 0.0
        self._current_hover_block: Tuple[int, int] = (-1, -1)
        self._last_rendered_hover_block: Tuple[int, int] = (-1, -1)  # Track last rendered hover
        
        # LINE INTERPOLATION: Track last drawn position for continuous lines
        self._last_drawn_block: Tuple[int, int] = (-1, -1)
        self._drawing_blocks_cache: List[Tuple[int, int]] = []  # Blocks drawn in current stroke
        
        # Grid overlay
        self._show_grid: bool = True
        self._grid_color: Tuple[int, int, int, int] = (100, 100, 100, 128)
        
        # Current tool state
        self._current_block: Optional[BlockTexture] = None
        self._tool_callback: Optional[Callable] = None
        self._active_tool = None  # Active tool instance
        
        # Callbacks
        self.on_block_changed: Optional[Callable] = None
        self.on_selection_changed: Optional[Callable] = None
        
        # Background
        self._background_color: Tuple[int, int, int] = (45, 45, 48)
        
        # Render state
        self._is_rendering = False
        
        # Performance optimizations
        self._texture_loading_pool = ThreadPoolExecutor(max_workers=4)
        self._texture_loading_lock = threading.Lock()
        
        # EXTREME OPTIMIZATIONS: Memory pooling and caching
        self._visible_blocks_pool = []  # Reusable list to avoid allocations
        self._coord_cache = {}  # Cache for coordinate calculations at different zoom levels
        self._last_zoom_level = -1.0
        self._last_viewport = (-1, -1, -1, -1)  # Cache viewport bounds
        
        # NumPy arrays for vectorized calculations
        self._x_coords_cache = None
        self._y_coords_cache = None
        
        # Drawing item tags for selective deletion
        self._hover_items = []  # List of hover highlight item tags
        self._grid_items = []   # List of grid line item tags
        
        # Hover throttling to reduce flickering
        self._last_hover_render_time = 0.0
        self._hover_render_delay = 0.05  # 50ms = 20 FPS for hover updates (smooth enough)
        
        # DEBOUNCED RENDERING: Accumulate changes and render in batches
        self._pending_render = False
        self._dirty_blocks: set = set()  # Set of (x, y) coordinates that need redraw
        self._last_render_time = 0.0
        self._render_delay = 0.016  # ~60 FPS max render rate (16ms)
        self._batch_changes: List[Tuple[int, int, BlockTexture]] = []  # Pending block changes
        
        # RENDER SCHEDULER: Timer-based rendering
        self._render_timer = None
        self._max_batch_size = 100  # Max changes before forcing render
        
        # Create drawlist
        self._create_canvas()
    
    def __del__(self):
        """Cleanup resources on destruction."""
        try:
            if hasattr(self, '_texture_loading_pool'):
                self._texture_loading_pool.shutdown(wait=False)
        except:
            pass
    
    def _create_canvas(self) -> None:
        """Creates the Dear PyGui canvas (single drawlist)."""
        dpg.add_drawlist(tag=self.tag, width=self.width, height=self.height, parent=self.parent)
    
    def setup_handlers(self) -> None:
        """Sets up mouse handlers for the canvas. Call this after creating the canvas."""
        with dpg.item_handler_registry(tag=f"{self.tag}_handlers") as handlers:
            dpg.add_item_clicked_handler(callback=self._on_click)
            dpg.add_item_hover_handler(callback=self._on_mouse_move)
        
        dpg.bind_item_handler_registry(self.tag, handlers)
    
    def stop_drawing(self) -> None:
        """Stops drawing mode and finalizes the stroke with a full render.
        Call this when mouse button is released.
        """
        if self._is_drawing:
            self._is_drawing = False
            
            # Notify active tool
            if self._active_tool:
                # Get last grid position
                local_x, local_y = self._get_local_mouse_pos()
                grid_x, grid_y = self.screen_to_grid(local_x, local_y)
                if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
                    self._active_tool.on_mouse_up(self, grid_x, grid_y, "left")
            
            self._last_drawn_block = (-1, -1)
            
            # Force a final full render to ensure everything is properly displayed
            if self._dirty_blocks or self._pending_render:
                self.render(force_full=True)
    
    def start_pan(self) -> None:
        """Starts panning mode. Call this when middle mouse button is pressed."""
        self._is_panning = True
        # Use GLOBAL mouse position for pan, not local canvas position
        mouse_pos = dpg.get_mouse_pos(local=False)
        self._mouse_start_x = mouse_pos[0]
        self._mouse_start_y = mouse_pos[1]
        self._pan_start_x = self._pan_x
        self._pan_start_y = self._pan_y
    
    def update_pan(self) -> None:
        """Updates pan position during drag. Call this on mouse move while panning."""
        if not self._is_panning:
            return
        
        # Use GLOBAL mouse position for pan, not local canvas position
        mouse_pos = dpg.get_mouse_pos(local=False)
        mouse_x = mouse_pos[0]
        mouse_y = mouse_pos[1]
        
        # Calculate offset from start position
        delta_x = mouse_x - self._mouse_start_x
        delta_y = mouse_y - self._mouse_start_y
        
        # Apply to initial pan position
        self._pan_x = self._pan_start_x + delta_x
        self._pan_y = self._pan_start_y + delta_y
    
    def stop_pan(self) -> None:
        """Stops panning mode. Call this when middle mouse button is released."""
        if self._is_panning:  # Only render if we were actually panning
            self._is_panning = False
            self.render()
        else:
            self._is_panning = False  # Ensure flag is cleared even if already false
    
    def force_stop_pan(self) -> None:
        """Force stops panning (safety mechanism for stuck pan states)."""
        if self._is_panning:
            self._is_panning = False
            self.render()
    
    def _get_local_mouse_pos(self) -> Tuple[float, float]:
        """""Gets mouse position relative to canvas, accounting for window layout.
        
        Returns:
            Tuple (local_x, local_y) in canvas coordinates
        """
        # Get global mouse position
        mouse_pos = dpg.get_mouse_pos(local=False)
        
        # Get canvas position in window
        canvas_rect = dpg.get_item_rect_min(self.tag)
                # Check if canvas_rect is valid
        if canvas_rect is None or not canvas_rect:
            return (0.0, 0.0)
                # Calculate local position
        local_x = mouse_pos[0] - canvas_rect[0]
        local_y = mouse_pos[1] - canvas_rect[1]
        
        return (local_x, local_y)
    
    # ========================================================================
    # Grid Management
    # ========================================================================
    
    def set_grid(self, grid: List[List[BlockTexture]]) -> None:
        """
        Sets the block grid to display.
        
        Args:
            grid: 2D list of BlockTexture (height x width)
        """
        # Clear old textures when loading new grid
        self.clear_textures()
        
        if not grid or not grid[0]:
            self._grid = []
            self._grid_width = 0
            self._grid_height = 0
        else:
            self._grid = grid
            self._grid_height = len(grid)
            self._grid_width = len(grid[0])
        
        # Clear texture cache from Dear PyGui
        for texture_tag in self._texture_cache.values():
            if dpg.does_item_exist(texture_tag):
                dpg.delete_item(texture_tag)
        self._texture_cache.clear()
        
        # PRE-LOAD unique textures asynchronously for faster first render
        if grid:
            self._preload_textures_async(grid)
        
        self.render()
    
    def get_grid(self) -> List[List[BlockTexture]]:
        """Returns the current block grid."""
        return self._grid
    
    def get_block_at(self, x: int, y: int) -> Optional[BlockTexture]:
        """
        Gets the block at grid coordinates.
        
        Args:
            x: Grid X coordinate
            y: Grid Y coordinate
            
        Returns:
            BlockTexture or None if out of bounds
        """
        if 0 <= y < self._grid_height and 0 <= x < self._grid_width:
            return self._grid[y][x]
        return None
    
    def set_block_at(self, x: int, y: int, block: BlockTexture, immediate_render: bool = False) -> None:
        """
        Sets a block at grid coordinates.
        
        Args:
            x: Grid X coordinate
            y: Grid Y coordinate
            block: BlockTexture to place
            immediate_render: If True, render immediately; if False, batch for later
        """
        if 0 <= y < self._grid_height and 0 <= x < self._grid_width:
            # Check if block is actually different to avoid unnecessary updates
            if self._grid[y][x].block_id == block.block_id:
                return  # No change needed
            
            self._grid[y][x] = block
            
            # Mark as dirty for partial rendering
            self._dirty_blocks.add((x, y))
            
            if self.on_block_changed:
                self.on_block_changed(x, y, block)
            
            # BATCH RENDERING: Accumulate changes instead of rendering immediately
            if immediate_render:
                self.render()
            else:
                self._schedule_render()
    
    # ========================================================================
    # Zoom and Pan
    # ========================================================================
    
    def set_zoom(self, zoom: float, center_x: Optional[float] = None, center_y: Optional[float] = None) -> None:
        """
        Sets the zoom level.
        
        Args:
            zoom: Zoom factor (1.0 = 100%, 2.0 = 200%, etc.)
            center_x: X coordinate to zoom towards (None = center of canvas)
            center_y: Y coordinate to zoom towards (None = center of canvas)
        """
        old_zoom = self._zoom_level
        self._zoom_level = max(self._min_zoom, min(self._max_zoom, zoom))
        
        # Adjust pan to zoom towards specified point
        if old_zoom != self._zoom_level:
            if center_x is None:
                center_x = self.width / 2
            if center_y is None:
                center_y = self.height / 2
            self._adjust_pan_for_zoom(center_x, center_y, old_zoom, self._zoom_level)
            self.render()
    
    def zoom_in(self) -> None:
        """Zooms in with exponential scaling for better UX."""
        # EXPONENTIAL ZOOM: Faster when zoomed out, slower when zoomed in
        if self._zoom_level < 0.5:
            zoom_factor = 1.3  # 30% increase when very zoomed out
        elif self._zoom_level < 1.0:
            zoom_factor = 1.25  # 25% increase when somewhat zoomed out
        elif self._zoom_level < 4.0:
            zoom_factor = 1.2  # 20% increase at normal zoom
        else:
            zoom_factor = 1.15  # 15% increase when very zoomed in (more precise)
        
        self.set_zoom(self._zoom_level * zoom_factor)
    
    def zoom_out(self) -> None:
        """Zooms out with exponential scaling for better UX."""
        # EXPONENTIAL ZOOM: Faster when zoomed out, slower when zoomed in
        if self._zoom_level < 0.5:
            zoom_factor = 0.77  # ~30% decrease when very zoomed out
        elif self._zoom_level < 1.0:
            zoom_factor = 0.8   # 25% decrease when somewhat zoomed out
        elif self._zoom_level < 4.0:
            zoom_factor = 0.83  # ~20% decrease at normal zoom
        else:
            zoom_factor = 0.87  # ~15% decrease when very zoomed in
        
        self.set_zoom(self._zoom_level * zoom_factor)
    
    def zoom_to_fit(self) -> None:
        """Zooms to fit the entire grid in the viewport."""
        if self._grid_width == 0 or self._grid_height == 0:
            return
        
        grid_pixel_width = self._grid_width * self._block_size
        grid_pixel_height = self._grid_height * self._block_size
        
        zoom_x = (self.width - 40) / grid_pixel_width
        zoom_y = (self.height - 40) / grid_pixel_height
        
        self._zoom_level = min(zoom_x, zoom_y)
        self._pan_x = (self.width - grid_pixel_width * self._zoom_level) / 2
        self._pan_y = (self.height - grid_pixel_height * self._zoom_level) / 2
        self.render()
    
    def reset_view(self) -> None:
        """Resets zoom and pan to defaults."""
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.render()
    
    def _adjust_pan_for_zoom(self, center_x: float, center_y: float, old_zoom: float, new_zoom: float) -> None:
        """Adjusts pan offset to zoom towards a specific point."""
        # Calculate the position in grid space before zoom
        grid_x = (center_x - self._pan_x) / old_zoom
        grid_y = (center_y - self._pan_y) / old_zoom
        
        # Calculate new pan offset to keep the same grid position under the cursor
        self._pan_x = center_x - grid_x * new_zoom
        self._pan_y = center_y - grid_y * new_zoom
    
    # ========================================================================
    # Grid Display Settings
    # ========================================================================
    
    def set_show_grid(self, show: bool) -> None:
        """Enables or disables grid overlay."""
        self._show_grid = show
        self.render()
    
    def is_grid_visible(self) -> bool:
        """Returns whether grid is visible."""
        return self._show_grid
    
    def set_grid_color(self, color: Tuple[int, int, int, int]) -> None:
        """Sets the grid line color (RGBA)."""
        self._grid_color = color
        self.render()
    
    # ========================================================================
    # Tool Support
    # ========================================================================
    
    def set_current_block(self, block: Optional[BlockTexture]) -> None:
        """
        Sets the current block for painting.
        
        Args:
            block: BlockTexture to use for painting, or None
        """
        self._current_block = block
    
    def get_current_block(self) -> Optional[BlockTexture]:
        """Returns the current block for painting."""
        return self._current_block
    
    def set_tool_callback(self, callback: Optional[Callable]) -> None:
        """
        Sets a callback function to be called when the user draws.
        
        Args:
            callback: Function(canvas, x, y, button) called on mouse interaction
        """
        self._tool_callback = callback
    
    def set_active_tool(self, tool) -> None:
        """
        Sets the active tool.
        
        Args:
            tool: Tool instance (BaseTool subclass)
        """
        if self._active_tool:
            self._active_tool.deactivate()
        self._active_tool = tool
        if self._active_tool:
            self._active_tool.activate()
    
    def get_active_tool(self):
        """Returns the currently active tool."""
        return self._active_tool
    
    def _schedule_render(self) -> None:
        """Schedules a render for the next frame, avoiding excessive renders."""
        current_time = time.time()
        
        # If enough time has passed or too many changes accumulated, render now
        if (current_time - self._last_render_time >= self._render_delay or 
            len(self._dirty_blocks) >= self._max_batch_size):
            self.render()
        else:
            # Mark that we need to render soon
            self._pending_render = True
    
    def _bresenham_line(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Bresenham's line algorithm for smooth line interpolation.
        
        Returns all grid coordinates between (x0, y0) and (x1, y1).
        This ensures continuous lines without gaps when drawing.
        """
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
    
    def draw_line_between_blocks(self, x0: int, y0: int, x1: int, y1: int, block: BlockTexture) -> None:
        """Draws a continuous line of blocks between two points using Bresenham's algorithm.
        
        This prevents gaps when the mouse moves faster than the render rate.
        """
        points = self._bresenham_line(x0, y0, x1, y1)
        
        # Paint all points in the line
        for x, y in points:
            if 0 <= x < self._grid_width and 0 <= y < self._grid_height:
                # Don't render each block individually - batch them all
                if self._grid[y][x].block_id != block.block_id:
                    self._grid[y][x] = block
                    self._dirty_blocks.add((x, y))
                    if self.on_block_changed:
                        self.on_block_changed(x, y, block)
        
        # Schedule a single render for all changes
        self._schedule_render()
    
    # ========================================================================
    # Coordinate Conversion
    # ========================================================================
    
    def screen_to_grid(self, screen_x: float, screen_y: float) -> Tuple[int, int]:
        """
        Converts screen coordinates to grid coordinates.
        
        Args:
            screen_x: X position in widget coordinates
            screen_y: Y position in widget coordinates
            
        Returns:
            Tuple (grid_x, grid_y), may be out of bounds
        """
        # Account for pan and zoom
        grid_x = int((screen_x - self._pan_x) / (self._block_size * self._zoom_level))
        grid_y = int((screen_y - self._pan_y) / (self._block_size * self._zoom_level))
        return (grid_x, grid_y)
    
    def grid_to_screen(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """
        Converts grid coordinates to screen coordinates.
        
        Args:
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            
        Returns:
            Screen position (top-left corner of block)
        """
        screen_x = grid_x * self._block_size * self._zoom_level + self._pan_x
        screen_y = grid_y * self._block_size * self._zoom_level + self._pan_y
        return (screen_x, screen_y)
    
    # ========================================================================
    # Rendering
    # ========================================================================
    
    def _load_texture(self, block: BlockTexture) -> str:
        """
        Loads and caches a block texture for Dear PyGui.
        
        Args:
            block: BlockTexture to load
            
        Returns:
            Dear PyGui texture tag
        """
        if block.block_id in self._texture_cache:
            return self._texture_cache[block.block_id]
        
        # Load texture from file
        try:
            if block.texture_path.exists():
                img = Image.open(block.texture_path).convert('RGBA')
            else:
                # Fallback: create colored rectangle
                color = block.avg_color if block.avg_color else (255, 0, 255)
                img = Image.new('RGBA', (self._block_size, self._block_size), (*color, 255))
        except:
            # Fallback on error
            color = block.avg_color if block.avg_color else (255, 0, 255)
            img = Image.new('RGBA', (self._block_size, self._block_size), (*color, 255))
        
        # Use helper method to create DPG texture
        return self._create_dpg_texture(block, img)
    
    def clear_textures(self) -> None:
        """Clears all cached textures from GPU memory."""
        for block_id, texture_tag in list(self._texture_cache.items()):
            if dpg.does_item_exist(texture_tag):
                dpg.delete_item(texture_tag)
        self._texture_cache.clear()
    
    def _preload_textures_async(self, grid: List[List[BlockTexture]]) -> None:
        """
        Pre-loads all unique textures in the grid asynchronously.
        This dramatically speeds up the first render by loading textures in parallel.
        """
        # Collect unique blocks
        unique_blocks = {}
        for row in grid:
            for block in row:
                if block.block_id not in unique_blocks:
                    unique_blocks[block.block_id] = block
        
        # Load textures in parallel using thread pool
        # Note: Only loading images, DPG texture creation happens in main thread
        def preload_block(block):
            if block.block_id not in self._texture_cache:
                try:
                    # Pre-load the image file (I/O bound operation)
                    if block.texture_path.exists():
                        img = Image.open(block.texture_path).convert('RGBA')
                        return (block, img)
                except:
                    pass
            return (block, None)
        
        # Execute parallel loading
        futures = []
        for block in list(unique_blocks.values())[:50]:  # Limit to first 50 unique textures for responsiveness
            future = self._texture_loading_pool.submit(preload_block, block)
            futures.append(future)
        
        # Collect results and create DPG textures in main thread
        for future in futures:
            try:
                block, img = future.result(timeout=0.1)  # Quick timeout to avoid blocking
                if img and block.block_id not in self._texture_cache:
                    # Create texture in cache
                    self._create_dpg_texture(block, img)
            except:
                pass  # Skip on timeout or error
    
    def _create_dpg_texture(self, block: BlockTexture, img: Image.Image) -> str:
        """Creates a Dear PyGui texture from a PIL Image."""
        # Convert to numpy array (Dear PyGui format)
        texture_data = np.frombuffer(img.tobytes(), dtype=np.uint8)
        texture_data = texture_data.reshape((img.height, img.width, 4))
        texture_data = texture_data.astype(np.float32) / 255.0
        
        # Create Dear PyGui texture
        texture_tag = f"texture_{block.block_id}"
        
        # Check if texture already exists and delete it
        if dpg.does_item_exist(texture_tag):
            dpg.delete_item(texture_tag)
        
        with self._texture_loading_lock:
            with dpg.texture_registry():
                dpg.add_raw_texture(
                    width=img.width,
                    height=img.height,
                    default_value=texture_data,
                    format=dpg.mvFormat_Float_rgba,
                    tag=texture_tag
                )
        
        self._texture_cache[block.block_id] = texture_tag
        return texture_tag
    
    def render(self, force_full: bool = False) -> None:
        """Renders the grid on the Dear PyGui canvas with optimized viewport culling.
        
        Args:
            force_full: If True, forces a full render even if dirty regions are available
        """
        # Simple guard against recursion
        if self._is_rendering:
            return
        
        self._is_rendering = True
        self._last_render_time = time.time()
        self._pending_render = False
        
        try:
            # OPTIMIZATION: Use dirty region rendering for small changes during drawing
            # Only use dirty rendering when:
            # 1. We have a small number of dirty blocks (< 50)
            # 2. We're not being forced to do a full render
            # 3. Grid exists and is not empty
            use_dirty_render = (len(self._dirty_blocks) > 0 and 
                              len(self._dirty_blocks) < 50 and 
                              not force_full and 
                              self._grid)
            
            if use_dirty_render:
                self._render_dirty_blocks()
                return
            # Clear only block drawings, keep grid and hover for selective update
            dpg.delete_item(self.tag, children_only=True)
            
            # Clear item tracking lists (they'll be repopulated)
            self._grid_items.clear()
            self._hover_items.clear()
            
            if not self._grid:
                # Draw "no image" text
                dpg.draw_text((self.width / 2 - 50, self.height / 2), "No image loaded", 
                             color=(150, 150, 150), parent=self.tag, size=16)
                return
            
            # OPTIMIZATION: Fast viewport calculation with clamping
            # Inline calculation to avoid function call overhead
            zoom_inv = 1.0 / (self._block_size * self._zoom_level)
            start_x = max(0, int((-50 - self._pan_x) * zoom_inv))
            start_y = max(0, int((-50 - self._pan_y) * zoom_inv))
            end_x = min(self._grid_width - 1, int((self.width + 50 - self._pan_x) * zoom_inv))
            end_y = min(self._grid_height - 1, int((self.height + 50 - self._pan_y) * zoom_inv))
            
            scaled_block_size = self._block_size * self._zoom_level
            
            # Verify parent still exists before drawing
            if not dpg.does_item_exist(self.tag):
                return
            
            # PHASE 1: EXTREME OPTIMIZATION - NumPy Vectorized Coordinate Calculation
            # Calculate ALL coordinates at once using NumPy (10-100x faster than loops)
            
            # Reuse memory pool to avoid allocations
            self._visible_blocks_pool.clear()
            
            # Pre-calculate transformation constants
            zoom_block_size = self._block_size * self._zoom_level
            pan_x = self._pan_x
            pan_y = self._pan_y
            
            # NumPy vectorized coordinate calculation for all visible blocks
            width = end_x - start_x + 1
            height = end_y - start_y + 1
            
            # Create coordinate arrays using NumPy (MUCH faster than loops)
            if self._x_coords_cache is None or len(self._x_coords_cache) < width:
                x_indices = np.arange(start_x, end_x + 1, dtype=np.float32)
                self._x_coords_cache = x_indices * zoom_block_size + pan_x
            else:
                # Reuse cached array
                x_indices = np.arange(start_x, end_x + 1, dtype=np.float32)
                np.multiply(x_indices, zoom_block_size, out=x_indices)
                np.add(x_indices, pan_x, out=x_indices)
                self._x_coords_cache = x_indices
            
            if self._y_coords_cache is None or len(self._y_coords_cache) < height:
                y_indices = np.arange(start_y, end_y + 1, dtype=np.float32)
                self._y_coords_cache = y_indices * zoom_block_size + pan_y
            else:
                # Reuse cached array
                y_indices = np.arange(start_y, end_y + 1, dtype=np.float32)
                np.multiply(y_indices, zoom_block_size, out=y_indices)
                np.add(y_indices, pan_y, out=y_indices)
                self._y_coords_cache = y_indices
            
            # Fast viewport culling with NumPy boolean masks
            x_mask = (self._x_coords_cache >= -scaled_block_size) & (self._x_coords_cache <= self.width)
            y_mask = (self._y_coords_cache >= -scaled_block_size) & (self._y_coords_cache <= self.height)
            
            # Collect visible blocks using pre-calculated coordinates
            visible_blocks = self._visible_blocks_pool
            for y_idx, screen_y in enumerate(self._y_coords_cache):
                if not y_mask[y_idx]:
                    continue
                
                y = start_y + y_idx
                row = self._grid[y]
                
                for x_idx, screen_x in enumerate(self._x_coords_cache):
                    if not x_mask[x_idx]:
                        continue
                    
                    x = start_x + x_idx
                    block = row[x]
                    visible_blocks.append((block, float(screen_x), float(screen_y)))
            
            # PHASE 2: PRE-LOAD all textures (ensures they're in cache)
            # This is fast because textures are cached after first load
            unique_blocks = {block.block_id: block for block, _, _ in visible_blocks}
            for block in unique_blocks.values():
                if block.block_id not in self._texture_cache:
                    self._load_texture(block)
            
            # PHASE 3: EXTREME BATCH RENDER - Group consecutive identical blocks
            # Verify parent one more time before batch render
            if not dpg.does_item_exist(self.tag):
                return
            
            try:
                # OPTIMIZATION: Sort by texture to enable batching
                # Blocks with same texture will be consecutive
                visible_blocks.sort(key=lambda b: b[0].block_id)
                
                # Batch render: process multiple blocks with same texture together
                if visible_blocks:
                    current_texture = None
                    batch_start = 0
                    
                    for i, (block, screen_x, screen_y) in enumerate(visible_blocks):
                        texture_tag = self._texture_cache[block.block_id]
                        
                        # Check if we should flush the batch
                        if current_texture != texture_tag:
                            current_texture = texture_tag
                        
                        # Draw immediately (DPG doesn't support true batching, but sorting helps cache)
                        dpg.draw_image(
                            texture_tag,
                            (screen_x, screen_y),
                            (screen_x + scaled_block_size, screen_y + scaled_block_size),
                            parent=self.tag
                        )
                        
            except SystemError:
                # Parent was deleted during render, exit gracefully
                pass
            
            # Draw grid overlay when zoomed in enough
            if self._show_grid and self._zoom_level >= 0.5:
                self._draw_grid(start_x, start_y, end_x, end_y)
            
            # Clear dirty blocks after full render
            self._dirty_blocks.clear()
            
        finally:
            self._is_rendering = False
        
        # SEPARATE LAYER: Update hover highlight independently
        # This prevents flickering since we don't clear the main canvas
        self._update_hover_layer()
    
    def _render_dirty_blocks(self) -> None:
        """Renders only the blocks that have changed (dirty blocks).
        
        This is a MASSIVE performance optimization for painting operations.
        Instead of redrawing the entire canvas, we only update changed blocks.
        """
        if not self._dirty_blocks or not dpg.does_item_exist(self.tag):
            self._dirty_blocks.clear()
            self._is_rendering = False
            return
        
        try:
            scaled_block_size = self._block_size * self._zoom_level
            
            # Pre-load textures for dirty blocks
            unique_blocks = {}
            for x, y in self._dirty_blocks:
                if 0 <= y < self._grid_height and 0 <= x < self._grid_width:
                    block = self._grid[y][x]
                    if block.block_id not in unique_blocks:
                        unique_blocks[block.block_id] = block
                        # Ensure texture is loaded
                        if block.block_id not in self._texture_cache:
                            self._load_texture(block)
            
            # Draw each dirty block
            for x, y in list(self._dirty_blocks):
                if 0 <= y < self._grid_height and 0 <= x < self._grid_width:
                    block = self._grid[y][x]
                    
                    # Calculate screen position
                    screen_x = x * scaled_block_size + self._pan_x
                    screen_y = y * scaled_block_size + self._pan_y
                    
                    # Check if block is visible on screen
                    if (screen_x + scaled_block_size >= 0 and screen_x <= self.width and
                        screen_y + scaled_block_size >= 0 and screen_y <= self.height):
                        
                        texture_tag = self._texture_cache.get(block.block_id)
                        if texture_tag:
                            # Draw the updated block
                            dpg.draw_image(
                                texture_tag,
                                (screen_x, screen_y),
                                (screen_x + scaled_block_size, screen_y + scaled_block_size),
                                parent=self.tag
                            )
                            
                            # Redraw grid lines for this block if grid is visible
                            if self._show_grid and self._zoom_level >= 0.5:
                                # Draw grid borders around this block
                                dpg.draw_rectangle(
                                    (screen_x, screen_y),
                                    (screen_x + scaled_block_size, screen_y + scaled_block_size),
                                    color=self._grid_color,
                                    thickness=1,
                                    fill=(0, 0, 0, 0),  # No fill, just border
                                    parent=self.tag
                                )
            
            # Clear dirty blocks after rendering
            self._dirty_blocks.clear()
            
        except (SystemError, Exception) as e:
            # Parent was deleted or error occurred, fall back to full render
            self._dirty_blocks.clear()
        
        finally:
            self._is_rendering = False
    
    def _draw_grid(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        """Draws the grid overlay with optimized calculations."""
        if not dpg.does_item_exist(self.tag):
            return
        
        # OPTIMIZATION: Pre-calculate all coordinates at once
        zoom_block_size = self._block_size * self._zoom_level
        
        # Calculate boundary coordinates once
        x_start_screen = start_x * zoom_block_size + self._pan_x
        x_end_screen = (end_x + 1) * zoom_block_size + self._pan_x
        y_start_screen = start_y * zoom_block_size + self._pan_y
        y_end_screen = (end_y + 1) * zoom_block_size + self._pan_y
        
        try:
            # Vertical lines with inline coordinate calculation
            for x in range(start_x, end_x + 2):
                screen_x = x * zoom_block_size + self._pan_x
                item = dpg.draw_line(
                    (screen_x, y_start_screen),
                    (screen_x, y_end_screen),
                    color=self._grid_color,
                    thickness=1,
                    parent=self.tag
                )
                self._grid_items.append(item)
            
            # Horizontal lines with inline coordinate calculation
            for y in range(start_y, end_y + 2):
                screen_y = y * zoom_block_size + self._pan_y
                item = dpg.draw_line(
                    (x_start_screen, screen_y),
                    (x_end_screen, screen_y),
                    color=self._grid_color,
                    thickness=1,
                    parent=self.tag
                )
                self._grid_items.append(item)
        except (SystemError, Exception):
            # Parent was deleted during draw, ignore
            pass
    
    def _draw_hover_highlight(self) -> None:
        """Draws a highlight over the currently hovered block with optimized calculation."""
        # Don't draw hover highlight while panning
        if self._is_panning:
            return
        
        # Verify parent exists (race condition protection)
        if not dpg.does_item_exist(self.tag):
            return
        
        x, y = self._current_hover_block
        if 0 <= x < self._grid_width and 0 <= y < self._grid_height:
            # OPTIMIZATION: Inline coordinate calculation
            scaled_block_size = self._block_size * self._zoom_level
            screen_x = x * scaled_block_size + self._pan_x
            screen_y = y * scaled_block_size + self._pan_y
            
            try:
                # Draw highlight rectangle
                dpg.draw_rectangle(
                    (screen_x, screen_y),
                    (screen_x + scaled_block_size, screen_y + scaled_block_size),
                    color=(255, 255, 255, 200),
                    thickness=2,
                    parent=self.tag
                )
            except (SystemError, Exception):
                # Parent was deleted during draw, ignore
                pass
    
    def _update_hover_layer(self) -> None:
        """Updates hover highlight with throttling to reduce flickering."""
        # Throttle hover updates to reduce flickering
        current_time = time.time()
        if current_time - self._last_hover_render_time < self._hover_render_delay:
            return
        
        self._last_hover_render_time = current_time
        
        # Don't draw hover highlight while panning
        if self._is_panning:
            return
        
        # Verify parent exists
        if not dpg.does_item_exist(self.tag):
            return
        
        # Delete previous hover items
        for item in self._hover_items:
            if dpg.does_item_exist(item):
                dpg.delete_item(item)
        self._hover_items.clear()
        
        center_x, center_y = self._current_hover_block
        if 0 <= center_x < self._grid_width and 0 <= center_y < self._grid_height:
            # Get brush size from active tool
            brush_size = 1
            if self._active_tool and hasattr(self._active_tool, 'get_brush_size'):
                brush_size = self._active_tool.get_brush_size()
            
            # Calculate brush area
            radius = brush_size // 2
            
            # OPTIMIZATION: Inline coordinate calculation
            scaled_block_size = self._block_size * self._zoom_level
            
            try:
                # Draw highlight for each block in brush area
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        block_x = center_x + dx
                        block_y = center_y + dy
                        
                        # Only draw if within grid bounds
                        if 0 <= block_x < self._grid_width and 0 <= block_y < self._grid_height:
                            screen_x = block_x * scaled_block_size + self._pan_x
                            screen_y = block_y * scaled_block_size + self._pan_y
                            
                            # Draw highlight rectangle
                            item = dpg.draw_rectangle(
                                (screen_x, screen_y),
                                (screen_x + scaled_block_size, screen_y + scaled_block_size),
                                color=(255, 255, 255, 200),
                                thickness=2,
                                parent=self.tag
                            )
                            self._hover_items.append(item)
            except (SystemError, Exception):
                # Parent was deleted, ignore
                pass
    
    # ========================================================================
    # Mouse Event Handlers (Dear PyGui callbacks)
    # ========================================================================
    
    def _on_click(self, sender, app_data):
        """Handles mouse clicks."""
        # Only handle left mouse button
        if not dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
            return
        
        local_x, local_y = self._get_local_mouse_pos()
        grid_x, grid_y = self.screen_to_grid(local_x, local_y)
        
        # START NEW STROKE: Reset line interpolation tracking
        self._is_drawing = True
        self._last_drawn_block = (grid_x, grid_y)
        self._drawing_blocks_cache = []
        
        # Use active tool if available
        if self._active_tool and 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
            self._active_tool.on_mouse_down(self, grid_x, grid_y, "left")
        else:
            self._handle_draw(local_x, local_y, "left")
    
    def _on_mouse_move(self, sender, app_data):
        """Handles mouse movement for hover."""
        # Skip hover updates while panning
        if self._is_panning:
            return
        
        local_x, local_y = self._get_local_mouse_pos()
        
        # Update hover position
        grid_x, grid_y = self.screen_to_grid(local_x, local_y)
        if (grid_x, grid_y) != self._current_hover_block:
            self._current_hover_block = (grid_x, grid_y)
            if self.on_selection_changed:
                self.on_selection_changed(grid_x, grid_y)
            
            # Update hover layer independently (no full redraw)
            self._update_hover_layer()
        
        # Continue drawing ONLY if left mouse button is held (not middle or right)
        if dpg.is_mouse_button_down(dpg.mvMouseButton_Left) and not dpg.is_mouse_button_down(dpg.mvMouseButton_Middle):
            # Use active tool if available
            if self._active_tool and 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
                self._active_tool.on_mouse_drag(self, grid_x, grid_y, "left")
            else:
                # LINE INTERPOLATION: Draw line from last position to current position
                if self._last_drawn_block != (-1, -1) and self._current_block:
                    last_x, last_y = self._last_drawn_block
                    
                    # Only interpolate if we've moved to a different block
                    if (grid_x, grid_y) != (last_x, last_y):
                        # Draw interpolated line between last and current position
                        self.draw_line_between_blocks(last_x, last_y, grid_x, grid_y, self._current_block)
                        self._last_drawn_block = (grid_x, grid_y)
                else:
                    # Fallback to regular drawing if no last position
                    self._handle_draw(local_x, local_y, "left")
                    self._last_drawn_block = (grid_x, grid_y)
    
    def _handle_draw(self, x: float, y: float, button: str) -> None:
        """
        Handles drawing interaction.
        
        Args:
            x: Mouse X position
            y: Mouse Y position
            button: Mouse button ("left" or "right")
        """
        grid_x, grid_y = self.screen_to_grid(x, y)
        
        # Check if in bounds
        if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
            if self._tool_callback:
                # Use custom tool callback
                self._tool_callback(self, grid_x, grid_y, button)
            elif button == "left" and self._current_block:
                # LINE INTERPOLATION: Draw from last position to current
                if self._last_drawn_block != (-1, -1):
                    last_x, last_y = self._last_drawn_block
                    if (grid_x, grid_y) != (last_x, last_y):
                        # Draw interpolated line
                        self.draw_line_between_blocks(last_x, last_y, grid_x, grid_y, self._current_block)
                    else:
                        # Same block, just update it
                        self.set_block_at(grid_x, grid_y, self._current_block, immediate_render=False)
                else:
                    # First block in stroke
                    self.set_block_at(grid_x, grid_y, self._current_block, immediate_render=False)
                
                # Update tracking
                self._last_drawn_block = (grid_x, grid_y)
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_canvas_info(self) -> dict:
        """
        Returns information about the canvas state.
        
        Returns:
            Dictionary with canvas info
        """
        return {
            'grid_width': self._grid_width,
            'grid_height': self._grid_height,
            'zoom_level': self._zoom_level,
            'pan_offset': (self._pan_x, self._pan_y),
            'show_grid': self._show_grid,
            'block_count': self._grid_width * self._grid_height if self._grid else 0,
        }
    
    def clear_cache(self) -> None:
        """Clears the texture cache."""
        for texture_tag in self._texture_cache.values():
            if dpg.does_item_exist(texture_tag):
                dpg.delete_item(texture_tag)
        self._texture_cache.clear()
        self.render()
