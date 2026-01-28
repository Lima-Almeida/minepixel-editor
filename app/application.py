"""
Main Application Module
Manages the Dear PyGui application lifecycle and coordinates all components.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import time
import dearpygui.dearpygui as dpg

from app.ui.canvas_widget import CanvasWidget
from app.ui.block_palette import BlockPaletteWidget
from app.core.block_manager import BlockManager
from app.core.exporter import Exporter
from app.minecraft.image_mapper import ImageToBlockMapper
from app.minecraft.texturepack.matcher import BlockMatcher
from app.tools.brush_tool import BrushTool
from app.tools.picker_tool import PickerTool


class MinepixelEditorApp:
    """Main application class for Minepixel Editor."""
    
    def __init__(self):
        # Core components
        self.canvas: Optional[CanvasWidget] = None
        self.block_manager: Optional[BlockManager] = None
        self.matcher: Optional[BlockMatcher] = None
        self.exporter = Exporter()
        self.block_palette: Optional[BlockPaletteWidget] = None
        
        # Tools
        self.brush_tool = BrushTool()
        self.picker_tool = PickerTool()
        self.active_tool = None
        
        # Application state
        self.last_loaded_image: Optional[Path] = None
        self._settings_initialized = False
        
        # UI tags
        self.status_text_tag = "status_text"
        self.progress_bar_tag = "progress_bar"
        self.status_group_tag = "status_group"
        self.sidebar_tag = "sidebar_window"
        self.left_panel_tag = "left_panel_window"
        self.toolbar_tag = "toolbar"
        self.tool_options_tag = "tool_options"
        self.block_stats_tag = "block_stats"
        self.settings_modal_tag = "settings_modal"
        self.settings_content_tag = "settings_content"
        self.active_search_tag = "active_search_input"
        self.ignored_search_tag = "ignored_search_input"
        self.export_dialog_tag = "export_file_dialog"
        self.export_image_dialog_tag = "export_image_dialog"
        
        # Lists for settings modal
        self._active_blocks_list = []
        self._ignored_blocks_list = []
        
        # Temporary data for image resize confirmation
        self._pending_image_path = None
        self._pending_resize_dimensions = None
        
    def setup(self):
        """Initialize Dear PyGui and setup UI."""
        dpg.create_context()
        
        # Create main window with canvas taking full space
        with dpg.window(label="Minepixel Editor - Minecraft Pixel Art Generator", 
                       tag="main_window", width=1860, height=850, pos=[10, 10]):
            
            # Menu bar at the top
            self._create_menu_bar()
            
            dpg.add_separator()
            
            # Canvas - takes up space between menu and footer
            self.canvas = CanvasWidget(tag="canvas", width=1840, height=760, parent="main_window")
        
        # Create status bar/footer as floating window (always on top)
        self._create_status_bar()
        
        # Create left panel as floating window over canvas
        self._create_left_panel()
        
        # Create right sidebar as floating window over canvas
        self._create_sidebar()
        
        # Setup canvas handlers
        self.canvas.setup_handlers()
        
        # Load blocks
        self._load_blocks()
        
        # Pre-load textures for modal
        self._preload_textures()
        
        # Setup global handlers
        self._setup_global_handlers()
        
        # Setup tools
        self._setup_tools()
        
        # Create viewport
        dpg.create_viewport(title="Minepixel Editor", width=1880, height=900)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        
        # Position floating panels
        dpg.set_item_pos(self.left_panel_tag, [20, 80])
        dpg.set_item_pos(self.sidebar_tag, [1490, 80])
        dpg.set_item_pos("status_bar_window", [10, 820])
        
        # Ensure status bar is always on top
        dpg.focus_item("status_bar_window")
    
    def _create_status_bar(self):
        """Creates the status bar as a floating window always on top."""
        with dpg.window(
            label="Status",
            tag="status_bar_window",
            width=1860,
            height=70,
            no_title_bar=True,
            no_move=True,
            no_resize=True,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True
        ):
            with dpg.group(horizontal=True, tag=self.status_group_tag):
                dpg.add_spacer(width=10)
                dpg.add_text("Loading textures...", tag=self.status_text_tag)
                dpg.add_spacer(width=20)
                dpg.add_progress_bar(
                    tag=self.progress_bar_tag,
                    default_value=0.0,
                    width=200,
                    show=False
                )
    
    def _create_header(self):
        """Creates the header bar as a floating window always on top."""
        with dpg.window(
            label="Header",
            tag="header_window",
            width=1860,
            height=50,
            no_title_bar=True,
            no_move=True,
            no_resize=True,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True
        ):
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=10)
                dpg.add_button(label="Load Image", callback=self._open_file_dialog, height=30)
                dpg.add_button(label="Export", callback=self._open_export_image_dialog, height=30)
                dpg.add_button(label="Settings", callback=self._open_settings_modal, height=30)
                dpg.add_spacer(width=20)
                dpg.add_button(label="Zoom +", callback=lambda: self.canvas.zoom_in(), height=30, width=70)
                dpg.add_button(label="Zoom -", callback=lambda: self.canvas.zoom_out(), height=30, width=70)
                dpg.add_button(label="Fit", callback=lambda: self.canvas.zoom_to_fit(), height=30, width=50)
                dpg.add_button(label="Grid", callback=self._toggle_grid, height=30, width=50)
    
    def _create_menu_bar(self):
        """Creates the top menu bar with all controls."""
        with dpg.group(horizontal=True):
            dpg.add_button(label="Load Image", callback=self._open_file_dialog)
            dpg.add_button(label="Export", callback=self._open_export_image_dialog)
            dpg.add_button(label="Settings", callback=self._open_settings_modal)
            dpg.add_spacer(width=10)
            dpg.add_button(label="Zoom +", callback=lambda: self.canvas.zoom_in())
            dpg.add_button(label="Zoom -", callback=lambda: self.canvas.zoom_out())
            dpg.add_button(label="Fit to Window", callback=lambda: self.canvas.zoom_to_fit())
            dpg.add_button(label="Reset View", callback=lambda: self.canvas.reset_view())
            dpg.add_button(label="Toggle Grid", callback=self._toggle_grid)
    
    def _create_sidebar(self):
        """Creates the right sidebar as a floating window over the canvas."""
        with dpg.window(
            label="Block Statistics",
            tag=self.sidebar_tag,
            width=360,
            height=720,
            no_move=False,
            no_resize=True,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True
        ):
            # Header (fixed)
            dpg.add_text("Block Statistics")
            dpg.add_separator()
            dpg.add_text("Load an image to see statistics", tag="sidebar_placeholder")
            
            # Totals section (fixed, not scrollable)
            with dpg.group(tag=f"{self.block_stats_tag}_totals"):
                pass
            
            # Scrollable container for block stats list only
            with dpg.child_window(
                tag=f"{self.block_stats_tag}_scroll",
                width=-1,
                height=-60,  # Leave space for totals above and button below
                border=True
            ):
                with dpg.group(tag=self.block_stats_tag):
                    pass
            
            # Footer with export button (fixed at bottom)
            dpg.add_separator()
            dpg.add_button(label="Export Block List to TXT", callback=self._open_export_dialog,
                         width=-1, height=30)
    
    def _create_left_panel(self):
        """Creates the left panel as a floating window over the canvas."""
        with dpg.window(
            label="Tools",
            tag=self.left_panel_tag,
            width=290,
            height=720,
            no_move=False,
            no_resize=True,
            no_collapse=True,
            no_close=True
        ):
            # Toolbar section
            dpg.add_text("Toolbar", color=(200, 200, 255))
            dpg.add_separator()
            
            with dpg.group(tag=self.toolbar_tag):
                # Brush tool button
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="🖌️ Brush",
                        tag="tool_brush_btn",
                        width=130,
                        height=40,
                        callback=lambda: self._select_tool(self.brush_tool)
                    )
                    dpg.add_button(
                        label="💧 Eyedropper",
                        tag="tool_picker_btn",
                        width=130,
                        height=40,
                        callback=lambda: self._select_tool(self.picker_tool)
                    )
            
            dpg.add_separator()
            
            # Tool options section
            dpg.add_text("Tool Options", color=(200, 200, 255))
            dpg.add_separator()
            
            with dpg.group(tag=self.tool_options_tag):
                dpg.add_text("Select a tool to see options")
            
            dpg.add_separator()
            
            # Selected block display (larger)
            dpg.add_text("Selected Block", color=(200, 200, 255))
            dpg.add_separator()
            
            with dpg.group(tag="selected_block_display"):
                with dpg.group(horizontal=True, tag="selected_block_container"):
                    # Texture will be added dynamically when a block is selected
                    with dpg.group(tag="selected_texture_group"):
                        pass
                    with dpg.group():
                        dpg.add_text("No block selected", tag="selected_block_name_large")
                        dpg.add_text("", tag="selected_block_info", color=(150, 150, 150))
            
            dpg.add_separator()
            
            # Block palette section
            dpg.add_text("Block Palette", color=(200, 200, 255))
            dpg.add_separator()
            
            # Create block palette widget (reduced height)
            self.block_palette = BlockPaletteWidget(
                tag="block_palette",
                width=270,
                height=320,
                parent=self.left_panel_tag
            )
    
    def _setup_tools(self):
        """Setup tools and their connections."""
        # Set picker callback
        self.picker_tool.set_on_block_picked(self._on_block_picked_by_picker)
        
        # Select brush tool by default
        self._select_tool(self.brush_tool)
        
        # Connect block palette to canvas
        if self.block_palette:
            self.block_palette.set_on_block_selected(self._on_palette_block_selected)
    
    def _select_tool(self, tool):
        """Selects a tool and updates UI."""
        self.active_tool = tool
        self.canvas.set_active_tool(tool)
        
        # Update tool option panel
        self._update_tool_options()
        
        # Update button highlights
        self._update_tool_button_highlights()
        
        # Update status
        dpg.set_value(self.status_text_tag, f"Tool selected: {tool.name}")
    
    def _update_tool_options(self):
        """Updates the tool options panel based on active tool."""
        # Clear existing options
        if dpg.does_item_exist(self.tool_options_tag):
            dpg.delete_item(self.tool_options_tag, children_only=True)
        
        if isinstance(self.active_tool, BrushTool):
            # Show brush size options
            with dpg.group(parent=self.tool_options_tag):
                dpg.add_text("Brush Size:")
                
                current_size = self.active_tool.get_brush_size()
                
                # Slider with odd values only (1, 3, 5, 7, 9, 11, 13, 15)
                dpg.add_slider_int(
                    label="Size",
                    tag="brush_size_slider",
                    default_value=current_size,
                    min_value=1,
                    max_value=15,
                    callback=self._on_brush_size_changed,
                    width=200,
                    clamped=True
                )
                
                dpg.add_text(f"Current: {current_size}x{current_size}", tag="brush_size_text")
                
                # Quick size buttons
                dpg.add_text("Quick Select:")
                with dpg.group(horizontal=True):
                    for size in [1, 3, 5, 7, 9]:
                        dpg.add_button(
                            label=f"{size}x{size}",
                            width=50,
                            callback=lambda s, a, u: self._set_brush_size(u),
                            user_data=size
                        )
        
        elif isinstance(self.active_tool, PickerTool):
            # Show picker info
            with dpg.group(parent=self.tool_options_tag):
                dpg.add_text("Click on canvas to pick a block")
                dpg.add_text("The picked block will be selected")
                dpg.add_text("in the palette.")
    
    def _update_tool_button_highlights(self):
        """Updates tool button highlights."""
        # Reset all buttons
        if dpg.does_item_exist("tool_brush_btn"):
            dpg.configure_item("tool_brush_btn", show=True)
        if dpg.does_item_exist("tool_picker_btn"):
            dpg.configure_item("tool_picker_btn", show=True)
        
        # Note: DPG doesn't have easy button highlighting
        # In a more advanced implementation, could change button colors
    
    def _on_brush_size_changed(self, sender, value):
        """Handles brush size slider change."""
        if isinstance(self.active_tool, BrushTool):
            # Ensure odd value
            if value % 2 == 0:
                value = value + 1 if value < 15 else value - 1
            
            self.active_tool.set_brush_size(value)
            
            # Update slider to odd value
            if dpg.does_item_exist("brush_size_slider"):
                dpg.set_value("brush_size_slider", value)
            
            if dpg.does_item_exist("brush_size_text"):
                dpg.set_value("brush_size_text", f"Current: {value}x{value}")
    
    def _set_brush_size(self, size):
        """Sets brush size from quick select buttons."""
        if isinstance(self.active_tool, BrushTool):
            self.active_tool.set_brush_size(size)
            if dpg.does_item_exist("brush_size_slider"):
                dpg.set_value("brush_size_slider", size)
            if dpg.does_item_exist("brush_size_text"):
                dpg.set_value("brush_size_text", f"Current: {size}x{size}")
    
    def _on_palette_block_selected(self, block):
        """Handles block selection from palette."""
        if self.canvas:
            self.canvas.set_current_block(block)
            self._update_selected_block_display(block)
            dpg.set_value(self.status_text_tag, f"Block selected: {block.block_id}")
    
    def _on_block_picked_by_picker(self, block):
        """Handles block picked by eyedropper tool."""
        # Update palette selection
        if self.block_palette:
            self.block_palette.set_selected_block(block)
        
        self._update_selected_block_display(block)
        dpg.set_value(self.status_text_tag, f"Block picked: {block.block_id}")
    
    def _update_selected_block_display(self, block):
        """Updates the large selected block display."""
        if not block:
            dpg.set_value("selected_block_name_large", "No block selected")
            dpg.set_value("selected_block_info", "")
            # Remove texture if exists
            if dpg.does_item_exist("selected_block_texture"):
                dpg.delete_item("selected_block_texture")
            return
        
        # Update text
        dpg.set_value("selected_block_name_large", block.block_id)
        
        # Add info about transparency if applicable
        info = "Solid block"
        if hasattr(block, 'has_transparency') and block.has_transparency:
            info = "Has transparency"
        dpg.set_value("selected_block_info", info)
        
        # Update texture
        texture_tag = f"selected_display_{block.block_id}"
        
        # Check if texture already exists
        if not dpg.does_item_exist(texture_tag):
            # Load and create texture
            from PIL import Image
            import numpy as np
            
            try:
                if block.texture_path.exists():
                    img = Image.open(block.texture_path).convert('RGBA')
                    img = img.resize((48, 48), Image.NEAREST)
                else:
                    color = block.avg_color if block.avg_color else (255, 0, 255)
                    img = Image.new('RGBA', (48, 48), (*color, 255))
            except:
                color = block.avg_color if block.avg_color else (255, 0, 255)
                img = Image.new('RGBA', (48, 48), (*color, 255))
            
            # Convert to DPG format
            texture_data = np.frombuffer(img.tobytes(), dtype=np.uint8)
            texture_data = texture_data.reshape((img.height, img.width, 4))
            texture_data = texture_data.astype(np.float32) / 255.0
            
            with dpg.texture_registry():
                dpg.add_raw_texture(
                    width=48,
                    height=48,
                    default_value=texture_data,
                    format=dpg.mvFormat_Float_rgba,
                    tag=texture_tag
                )
        
        # Update or create image widget
        if dpg.does_item_exist("selected_block_texture"):
            dpg.configure_item("selected_block_texture", texture_tag=texture_tag)
        else:
            # Create image widget for the first time
            if dpg.does_item_exist("selected_texture_group"):
                dpg.add_image(
                    texture_tag,
                    tag="selected_block_texture",
                    width=48,
                    height=48,
                    parent="selected_texture_group"
                )
    
    def _setup_global_handlers(self):
        """Setup global keyboard and mouse handlers."""
        with dpg.handler_registry():
            # Keyboard shortcuts
            dpg.add_key_press_handler(ord('+'), callback=lambda: self.canvas.zoom_in())
            dpg.add_key_press_handler(ord('='), callback=lambda: self.canvas.zoom_in())
            dpg.add_key_press_handler(ord('-'), callback=lambda: self.canvas.zoom_out())
            dpg.add_key_press_handler(ord('0'), callback=lambda: self.canvas.reset_view())
            dpg.add_key_press_handler(ord('F'), callback=lambda: self.canvas.zoom_to_fit())
            dpg.add_key_press_handler(ord('f'), callback=lambda: self.canvas.zoom_to_fit())
            dpg.add_key_press_handler(ord('G'), callback=self._toggle_grid)
            dpg.add_key_press_handler(ord('g'), callback=self._toggle_grid)
            
            # Mouse handlers
            dpg.add_mouse_wheel_handler(callback=self._on_mouse_scroll)
            dpg.add_mouse_down_handler(button=dpg.mvMouseButton_Middle, callback=self._on_pan_start)
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Middle, callback=self._on_pan_stop)
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Left, callback=self._on_draw_stop)
            dpg.add_mouse_move_handler(callback=self._on_mouse_move)
    
    def _load_blocks(self):
        """Load and initialize blocks."""
        texture_path = Path("assets/minecraft_textures/blocks")
        self.block_manager = BlockManager(texture_path)
        self.block_manager.load_blocks()
        
        # Initialize matcher
        self.matcher = BlockMatcher(self.block_manager.active_blocks)
        
        # Populate block palette
        if self.block_palette:
            self.block_palette.set_blocks(self.block_manager.active_blocks)
            # Set first block as default if available
            if self.block_manager.active_blocks:
                first_block = self.block_manager.active_blocks[0]
                self.block_palette.set_selected_block(first_block)
                self.canvas.set_current_block(first_block)
                self._update_selected_block_display(first_block)
        
        # Update status
        active_count = len(self.block_manager.active_blocks)
        total_count = len(self.block_manager.all_blocks)
        ignored_count = total_count - active_count
        
        dpg.set_value(self.status_text_tag, 
                     f"Loaded {total_count} textures ({active_count} active, {ignored_count} ignored)")
        
        # Create test grid
        self._create_test_grid()
    
    def _create_test_grid(self):
        """Creates a test grid with active blocks."""
        if not self.block_manager or not self.block_manager.active_blocks:
            dpg.set_value(self.status_text_tag, 
                        "ERROR: No active blocks available")
            return
        
        # Get solid blocks
        solid_blocks = [b for b in self.block_manager.active_blocks if not b.has_transparency]
        if len(solid_blocks) < 10:
            solid_blocks = self.block_manager.active_blocks
        
        # Create pattern grid
        grid_width = 32
        grid_height = 24
        
        grid = []
        for y in range(grid_height):
            row = []
            for x in range(grid_width):
                block_index = (x + y) % len(solid_blocks)
                row.append(solid_blocks[block_index])
            grid.append(row)
        
        self.canvas.set_grid(grid)
        self.canvas.zoom_to_fit()
        
        # Set current block for painting
        if solid_blocks:
            self.canvas.set_current_block(solid_blocks[0])
        
        # Connect callbacks
        self.canvas.on_block_changed = self._on_block_changed
        self.canvas.on_selection_changed = self._on_selection_changed
        
        # Update sidebar
        self._update_sidebar_stats(grid)
    
    def _preload_textures(self):
        """Pre-load block textures for modal performance."""
        if not self.block_manager or not self.block_manager.all_blocks:
            return
        
        from PIL import Image
        import numpy as np
        
        print("[INFO] Pre-loading textures for modal...")
        loaded = 0
        
        for block in self.block_manager.all_blocks:
            texture_tag = f"mini_{block.block_id}"
            if not dpg.does_item_exist(texture_tag) and block.texture_path.exists():
                try:
                    with Image.open(block.texture_path) as img:
                        img = img.resize((16, 16), Image.NEAREST)
                        img_array = np.array(img.convert('RGBA'), dtype=np.float32) / 255.0
                        with dpg.texture_registry():
                            dpg.add_static_texture(width=16, height=16, 
                                                 default_value=img_array.flatten().tolist(),
                                                 tag=texture_tag)
                        loaded += 1
                except Exception:
                    pass
        
        print(f"[INFO] Pre-loaded {loaded} textures")
    
    def _toggle_grid(self):
        """Toggle grid visibility."""
        if self.canvas:
            self.canvas.set_show_grid(not self.canvas.is_grid_visible())
    
    def _on_block_changed(self, x, y, block):
        """Called when a block is changed (painted)."""
        if not self.canvas:
            return
        
        info = self.canvas.get_canvas_info()
        dpg.set_value(self.status_text_tag,
            f"Block changed at ({x}, {y}) -> {block.block_id} | "
            f"Zoom: {info['zoom_level']:.1f}x | Grid: {info['grid_width']}x{info['grid_height']}")
    
    def _on_selection_changed(self, x, y):
        """Called when hover position changes."""
        if not self.canvas:
            return
        
        if 0 <= x < self.canvas._grid_width and 0 <= y < self.canvas._grid_height:
            block = self.canvas.get_block_at(x, y)
            if block:
                info = self.canvas.get_canvas_info()
                dpg.set_value(self.status_text_tag,
                    f"Hover: ({x}, {y}) -> {block.block_id} | "
                    f"Zoom: {info['zoom_level']:.1f}x | "
                    f"Left Click: Paint | Middle Click: Pan | Scroll: Zoom")
    
    # Mouse/Keyboard event handlers
    def _on_mouse_scroll(self, sender, app_data):
        """Handle mouse scroll for zoom."""
        # Only zoom if mouse is NOT over floating panels
        if self.canvas:
            # Check if mouse is over any floating panel
            if (dpg.is_item_hovered(self.left_panel_tag) or 
                dpg.is_item_hovered(self.sidebar_tag) or
                dpg.is_item_hovered("status_bar_window")):
                # Let the default scroll behavior handle it for panels
                return
            
            # Otherwise, handle zoom on canvas
            if dpg.is_item_hovered("canvas"):
                delta = app_data
                if delta > 0:
                    self.canvas.zoom_in()
                else:
                    self.canvas.zoom_out()
    
    def _on_pan_start(self):
        """Start pan mode."""
        # Only start pan if mouse is over canvas
        if self.canvas and dpg.is_item_hovered("canvas"):
            if not self.canvas._is_panning:  # Prevent multiple calls
                self.canvas.start_pan()
    
    def _on_pan_stop(self):
        """Stop pan mode."""
        if self.canvas:
            self.canvas.stop_pan()
    
    def _on_draw_stop(self):
        """Stop drawing mode and finalize stroke."""
        if self.canvas:
            self.canvas.stop_drawing()
    
    def _on_mouse_move(self, sender, app_data):
        """Handle mouse move for panning."""
        if self.canvas and self.canvas._is_panning:
            # Verify middle button is still pressed
            if dpg.is_mouse_button_down(dpg.mvMouseButton_Middle):
                self.canvas.update_pan()
                # Don't render during pan - only update position
                # This eliminates flicker completely
            else:
                # Button was released but event wasn't caught - force stop
                self.canvas.force_stop_pan()
    
    def run(self):
        """Run the application main loop."""
        dpg.show_metrics()
        
        while dpg.is_dearpygui_running():
            # Update canvas during pan (smooth rendering in main loop at 60 FPS)
            if self.canvas and self.canvas._is_panning:
                current_time = time.time()
                # Render at 60 FPS during pan for smooth visual feedback
                if current_time - self.canvas._last_pan_render_time >= self.canvas._pan_render_delay:
                    self.canvas._last_pan_render_time = current_time
                    self.canvas.render()
            
            # Process pending renders from canvas
            elif self.canvas and self.canvas._pending_render:
                current_time = time.time()
                if current_time - self.canvas._last_render_time >= self.canvas._render_delay:
                    self.canvas.render()
            
            dpg.render_dearpygui_frame()
        
        dpg.destroy_context()
    
    # File dialogs
    def _open_file_dialog(self):
        """Opens file dialog to load an image."""
        with dpg.file_dialog(
            directory_selector=False,
            show=True,
            callback=self._load_and_convert_image,
            file_count=1,
            width=700,
            height=400,
            default_path=str(Path.cwd())
        ):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".png", color=(0, 255, 0, 255))
            dpg.add_file_extension(".jpg", color=(255, 255, 0, 255))
            dpg.add_file_extension(".jpeg", color=(255, 255, 0, 255))
            dpg.add_file_extension(".bmp", color=(255, 128, 0, 255))
            dpg.add_file_extension(".gif", color=(128, 0, 255, 255))
    
    def _open_export_dialog(self):
        """Opens file dialog to export block list."""
        block_stats = self.exporter.analyze_grid_blocks(
            self.canvas._grid,
            BlockManager.get_base_block_name,
            BlockManager.get_block_variant
        )
        
        if not block_stats:
            dpg.set_value(self.status_text_tag, "No blocks to export. Load an image first.")
            return
        
        # Store stats for export callback
        self._pending_export_stats = block_stats
        
        # Create dialog if not exists
        if not dpg.does_item_exist(self.export_dialog_tag):
            with dpg.file_dialog(directory_selector=False, show=False, 
                               callback=self._export_block_list,
                               tag=self.export_dialog_tag,
                               width=700, height=400,
                               default_filename="block_list.txt"):
                dpg.add_file_extension(".txt", color=(150, 255, 150, 255))
        
        dpg.show_item(self.export_dialog_tag)
    
    def _open_export_image_dialog(self):
        """Opens file dialog to export canvas as image."""
        if not self.canvas or not self.canvas._grid:
            dpg.set_value(self.status_text_tag, "No image to export. Load an image first.")
            return
        
        # Create dialog if not exists
        if not dpg.does_item_exist(self.export_image_dialog_tag):
            with dpg.file_dialog(directory_selector=False, show=False, 
                               callback=self._export_canvas_image,
                               tag=self.export_image_dialog_tag,
                               width=700, height=400,
                               default_filename="minecraft_pixelart.png"):
                dpg.add_file_extension(".png", color=(150, 255, 150, 255))
        
        dpg.show_item(self.export_image_dialog_tag)
    
    def _load_and_convert_image(self, sender, app_data):
        """Loads and converts selected image."""
        selections = app_data.get('selections', {})
        if not selections:
            dpg.set_value(self.status_text_tag, "No file selected")
            return
        
        file_path = Path(list(selections.values())[0])
        if not file_path.exists():
            dpg.set_value(self.status_text_tag, f"ERROR: File not found: {file_path}")
            return
        
        # Check image size and show resize confirmation if needed
        try:
            from PIL import Image
            
            with Image.open(file_path) as img:
                width, height = img.size
            
            # Check if resize is needed (max 256x256)
            max_dimension = 256
            needs_resize = width > max_dimension or height > max_dimension
            
            if needs_resize:
                # Calculate proportional resize
                scale = max_dimension / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Store for later use
                self._pending_image_path = file_path
                self._pending_resize_dimensions = (new_width, new_height)
                
                # Show confirmation popup
                self._show_resize_confirmation_popup(file_path, width, height, new_width, new_height)
            else:
                # Load directly without resize
                self.last_loaded_image = file_path
                self._convert_and_load_image(file_path)
                
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR loading image: {e}")
            return
    
    def _export_block_list(self, sender, app_data):
        """Exports block list to TXT file."""
        try:
            file_path = Path(app_data['file_path_name'])
            if file_path.suffix.lower() != '.txt':
                file_path = file_path.with_suffix('.txt')
            
            self.exporter.export_block_list(self._pending_export_stats, file_path)
            dpg.set_value(self.status_text_tag, f"Exported block list to {file_path.name}")
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"Export ERROR: {e}")
    
    def _export_canvas_image(self, sender, app_data):
        """Exports canvas as PNG image."""
        try:
            file_path = Path(app_data['file_path_name'])
            if file_path.suffix.lower() != '.png':
                file_path = file_path.with_suffix('.png')
            
            dpg.set_value(self.status_text_tag, f"Exporting image to {file_path.name}...")
            self.exporter.export_image(self.canvas._grid, file_path)
            dpg.set_value(self.status_text_tag, f"Exported image to {file_path.name}")
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"Export ERROR: {e}")
    
    def _show_resize_confirmation_popup(self, file_path: Path, orig_width: int, orig_height: int, 
                                       new_width: int, new_height: int):
        """Shows a popup to confirm image resize."""
        popup_tag = "resize_confirmation_popup"
        
        # Delete existing popup if any
        if dpg.does_item_exist(popup_tag):
            dpg.delete_item(popup_tag)
        
        with dpg.window(
            label="Image Resize Required",
            tag=popup_tag,
            modal=True,
            show=True,
            width=500,
            height=250,
            pos=[690, 325],
            no_resize=True,
            no_move=True
        ):
            dpg.add_text("The selected image exceeds the maximum size of 256x256 pixels.")
            dpg.add_spacer(height=5)
            dpg.add_text(f"Original size: {orig_width}x{orig_height} pixels")
            dpg.add_text(f"Will be resized to: {new_width}x{new_height} pixels")
            dpg.add_spacer(height=5)
            dpg.add_text("This ensures the final pixel art fits within Minecraft's")
            dpg.add_text("performance limits (256x256 blocks maximum).")
            dpg.add_spacer(height=15)
            
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=120)
                dpg.add_button(
                    label="Accept and Import",
                    callback=lambda: self._confirm_resize_and_load(popup_tag),
                    width=130,
                    height=30
                )
                dpg.add_spacer(width=10)
                dpg.add_button(
                    label="Cancel",
                    callback=lambda: self._cancel_resize(popup_tag),
                    width=80,
                    height=30
                )
    
    def _confirm_resize_and_load(self, popup_tag: str):
        """Confirms resize and loads the image."""
        # Close popup
        if dpg.does_item_exist(popup_tag):
            dpg.delete_item(popup_tag)
        
        # Load image with resize
        self.last_loaded_image = self._pending_image_path
        self._convert_and_load_image(self._pending_image_path, target_size=self._pending_resize_dimensions)
    
    def _cancel_resize(self, popup_tag: str):
        """Cancels the resize operation."""
        # Close popup
        if dpg.does_item_exist(popup_tag):
            dpg.delete_item(popup_tag)
        
        dpg.set_value(self.status_text_tag, "Image import cancelled")
    
    def _convert_and_load_image(self, file_path: Path, target_size=None):
        """Converts and loads image to canvas."""
        try:
            from PIL import Image
            
            with Image.open(file_path) as img:
                width, height = img.size
            
            # Use target_size if provided, otherwise use original
            display_size = target_size if target_size else (width, height)
            
            dpg.set_value(self.status_text_tag, 
                f"Converting {file_path.name} ({display_size[0]}x{display_size[1]}) to blocks...")
            self._show_progress(0.0)
            
            # Convert image
            mapper = ImageToBlockMapper(self.matcher)
            
            def update_progress(progress):
                self._show_progress(progress)
            
            block_grid = mapper.map_image(file_path, target_size=target_size, progress_callback=update_progress)
            
            # Render
            dpg.set_value(self.status_text_tag, f"Rendering {file_path.name}...")
            self._show_progress(0.9)
            
            self.canvas.set_grid(block_grid)
            self.canvas.render()
            
            self._show_progress(0.95)
            self.canvas.zoom_to_fit()
            self.canvas.render()
            
            # Update stats
            self._update_sidebar_stats(block_grid)
            
            # Set current block
            if self.block_manager.active_blocks:
                solid = [b for b in self.block_manager.active_blocks if not b.has_transparency]
                if solid:
                    self.canvas.set_current_block(solid[0])
            
            # Ensure callbacks are connected
            self.canvas.on_block_changed = self._on_block_changed
            self.canvas.on_selection_changed = self._on_selection_changed
            
            grid_height = len(block_grid)
            grid_width = len(block_grid[0]) if grid_height > 0 else 0
            
            self._show_progress(1.0)
            dpg.set_value(self.status_text_tag,
                f"Loaded {file_path.name} | Grid: {grid_width}x{grid_height} blocks | "
                f"Original: {width}x{height} px")
            
            self._hide_progress()
            
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR: {e}")
            self._hide_progress()
            import traceback
            traceback.print_exc()
    
    def _show_progress(self, progress: float):
        """Shows and updates progress bar."""
        if dpg.does_item_exist(self.progress_bar_tag):
            dpg.set_value(self.progress_bar_tag, progress)
            dpg.show_item(self.progress_bar_tag)
    
    def _hide_progress(self):
        """Hides progress bar."""
        if dpg.does_item_exist(self.progress_bar_tag):
            dpg.hide_item(self.progress_bar_tag)
    
    def _update_sidebar_stats(self, grid):
        """Updates sidebar with block statistics."""
        # Clear previous stats from both containers
        if dpg.does_item_exist(self.block_stats_tag):
            dpg.delete_item(self.block_stats_tag, children_only=True)
        if dpg.does_item_exist(f"{self.block_stats_tag}_totals"):
            dpg.delete_item(f"{self.block_stats_tag}_totals", children_only=True)
        
        # Analyze
        block_stats = self.exporter.analyze_grid_blocks(
            grid,
            BlockManager.get_base_block_name,
            BlockManager.get_block_variant
        )
        
        if not block_stats:
            dpg.add_text("No blocks in grid", parent=self.block_stats_tag)
            return
        
        total_blocks = sum(stats['total'] for stats in block_stats.values())
        
        # Hide placeholder
        if dpg.does_item_exist("sidebar_placeholder"):
            dpg.hide_item("sidebar_placeholder")
        
        # Add totals to the fixed section (not scrollable)
        dpg.add_text(f"Total Blocks: {total_blocks:,}", parent=f"{self.block_stats_tag}_totals")
        dpg.add_text(f"Unique Types: {len(block_stats)}", parent=f"{self.block_stats_tag}_totals")
        dpg.add_separator(parent=f"{self.block_stats_tag}_totals")
        
        # Sort by count
        sorted_blocks = sorted(block_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Add blocks to scrollable list
        for base_name, stats in sorted_blocks:
            display_block = stats['blocks'].get('normal') or next(iter(stats['blocks'].values()))
            has_variants = len(stats['variants']) > 1
            
            if has_variants:
                with dpg.group(horizontal=True, parent=self.block_stats_tag):
                    if display_block and display_block.texture_path.exists():
                        self._add_mini_texture(display_block)
                    
                    with dpg.collapsing_header(label=f"{base_name}: {stats['total']} blocks",
                                              default_open=False):
                        for variant, count in sorted(stats['variants'].items()):
                            variant_block = stats['blocks'].get(variant)
                            if variant_block:
                                with dpg.group(horizontal=True):
                                    dpg.add_text(f"  • {variant.capitalize()}: {count}")
                                    if variant_block.texture_path.exists():
                                        self._add_mini_texture(variant_block)
            else:
                with dpg.group(horizontal=True, parent=self.block_stats_tag):
                    if display_block and display_block.texture_path.exists():
                        self._add_mini_texture(display_block)
                    dpg.add_text(f"{base_name}: {stats['total']}")
            
            dpg.add_spacer(height=4, parent=self.block_stats_tag)
    
    def _add_mini_texture(self, block):
        """Adds mini texture preview."""
        texture_tag = f"mini_{block.block_id}"
        if dpg.does_item_exist(texture_tag):
            dpg.add_image(texture_tag)
        else:
            from PIL import Image
            import numpy as np
            
            try:
                with Image.open(block.texture_path) as img:
                    img = img.resize((16, 16), Image.NEAREST)
                    img_array = np.array(img.convert('RGBA'), dtype=np.float32) / 255.0
                    with dpg.texture_registry():
                        dpg.add_static_texture(width=16, height=16, 
                                             default_value=img_array.flatten().tolist(),
                                             tag=texture_tag)
                    dpg.add_image(texture_tag)
            except Exception:
                pass
    
    def _open_settings_modal(self):
        """Opens settings modal for block management."""
        # Implementation will be added later (complex UI)
        dpg.set_value(self.status_text_tag, "Settings modal coming soon...")
