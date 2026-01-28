"""
Main Application Module
Manages the Dear PyGui application lifecycle and coordinates all components.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import dearpygui.dearpygui as dpg

from app.ui.canvas_widget import CanvasWidget
from app.core.block_manager import BlockManager
from app.core.exporter import Exporter
from app.minecraft.image_mapper import ImageToBlockMapper
from app.minecraft.texturepack.matcher import BlockMatcher


class MinepixelEditorApp:
    """Main application class for Minepixel Editor."""
    
    def __init__(self):
        # Core components
        self.canvas: Optional[CanvasWidget] = None
        self.block_manager: Optional[BlockManager] = None
        self.matcher: Optional[BlockMatcher] = None
        self.exporter = Exporter()
        
        # Application state
        self.last_loaded_image: Optional[Path] = None
        self._settings_initialized = False
        
        # UI tags
        self.status_text_tag = "status_text"
        self.progress_bar_tag = "progress_bar"
        self.status_group_tag = "status_group"
        self.sidebar_tag = "sidebar_window"
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
        
    def setup(self):
        """Initialize Dear PyGui and setup UI."""
        dpg.create_context()
        
        # Create main window
        with dpg.window(label="Minepixel Editor - Minecraft Pixel Art Generator", 
                       tag="main_window", width=1200, height=850):
            
            # Menu bar
            self._create_menu_bar()
            
            # Canvas
            self.canvas = CanvasWidget(tag="canvas", width=1180, height=750, parent="main_window")
            
            # Status bar with progress
            with dpg.group(horizontal=True, tag=self.status_group_tag):
                dpg.add_text("Loading textures...", tag=self.status_text_tag)
                dpg.add_spacer(width=20)
                dpg.add_progress_bar(tag=self.progress_bar_tag, default_value=0.0, 
                                   width=200, show=False)
        
        # Create floating sidebar
        self._create_sidebar()
        
        # Setup canvas handlers
        self.canvas.setup_handlers()
        
        # Load blocks
        self._load_blocks()
        
        # Pre-load textures for modal
        self._preload_textures()
        
        # Setup global handlers
        self._setup_global_handlers()
        
        # Create viewport
        dpg.create_viewport(title="Minepixel Editor", width=1580, height=870)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        
        # Position sidebar
        dpg.set_item_pos(self.sidebar_tag, [1210, 25])
    
    def _create_menu_bar(self):
        """Creates the top menu bar with all controls."""
        with dpg.group(horizontal=True):
            dpg.add_button(label="Load Image", callback=self._open_file_dialog)
            dpg.add_button(label="Export Image", callback=self._open_export_image_dialog)
            dpg.add_button(label="Settings", callback=self._open_settings_modal)
            dpg.add_button(label="Zoom In (+)", callback=lambda: self.canvas.zoom_in())
            dpg.add_button(label="Zoom Out (-)", callback=lambda: self.canvas.zoom_out())
            dpg.add_button(label="Fit to Window", callback=lambda: self.canvas.zoom_to_fit())
            dpg.add_button(label="Reset View", callback=lambda: self.canvas.reset_view())
            dpg.add_button(label="Toggle Grid", callback=self._toggle_grid)
    
    def _create_sidebar(self):
        """Creates the floating sidebar with statistics."""
        with dpg.window(label="Block Statistics", tag=self.sidebar_tag, 
                       width=360, height=820,
                       no_move=True, no_resize=False, no_collapse=True):
            dpg.add_text("Block Statistics")
            dpg.add_separator()
            dpg.add_text("Load an image to see statistics", tag="sidebar_placeholder")
            
            # Container for block stats
            with dpg.group(tag=self.block_stats_tag):
                pass
            
            # Export button
            dpg.add_separator()
            dpg.add_button(label="Export Block List to TXT", callback=self._open_export_dialog,
                         width=-1, height=30)
    
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
            dpg.add_mouse_move_handler(callback=self._on_mouse_move)
    
    def _load_blocks(self):
        """Load and initialize blocks."""
        texture_path = Path("assets/minecraft_textures/blocks")
        self.block_manager = BlockManager(texture_path)
        self.block_manager.load_blocks()
        
        # Initialize matcher
        self.matcher = BlockMatcher(self.block_manager.active_blocks)
        
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
    
    # Mouse/Keyboard event handlers
    def _on_mouse_scroll(self, sender, app_data):
        """Handle mouse scroll for zoom."""
        if self.canvas and dpg.is_item_hovered("canvas"):
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
    
    def _on_mouse_move(self, sender, app_data):
        """Handle mouse move for panning."""
        if self.canvas and self.canvas._is_panning:
            self.canvas.update_pan()
            self.canvas.render()  # Render during pan for smooth movement
    
    def run(self):
        """Run the application main loop."""
        dpg.show_metrics()
        
        while dpg.is_dearpygui_running():
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
        
        self.last_loaded_image = file_path
        self._convert_and_load_image(file_path)
    
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
    
    def _convert_and_load_image(self, file_path: Path):
        """Converts and loads image to canvas."""
        try:
            from PIL import Image
            
            with Image.open(file_path) as img:
                width, height = img.size
            
            dpg.set_value(self.status_text_tag, 
                f"Converting {file_path.name} ({width}x{height}) to blocks...")
            self._show_progress(0.0)
            
            # Convert image
            mapper = ImageToBlockMapper(self.matcher)
            
            def update_progress(progress):
                self._show_progress(progress)
            
            block_grid = mapper.map_image(file_path, target_size=None, progress_callback=update_progress)
            
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
        # Clear previous
        if dpg.does_item_exist(self.block_stats_tag):
            dpg.delete_item(self.block_stats_tag, children_only=True)
        
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
        
        # Add totals
        dpg.add_text(f"Total Blocks: {total_blocks:,}", parent=self.block_stats_tag)
        dpg.add_text(f"Unique Types: {len(block_stats)}", parent=self.block_stats_tag)
        dpg.add_separator(parent=self.block_stats_tag)
        
        # Sort by count
        sorted_blocks = sorted(block_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Scrollable list
        with dpg.child_window(parent=self.block_stats_tag, height=650, width=320):
            for base_name, stats in sorted_blocks:
                display_block = stats['blocks'].get('normal') or next(iter(stats['blocks'].values()))
                has_variants = len(stats['variants']) > 1
                
                if has_variants:
                    with dpg.group(horizontal=True):
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
                    with dpg.group(horizontal=True):
                        if display_block and display_block.texture_path.exists():
                            self._add_mini_texture(display_block)
                        dpg.add_text(f"{base_name}: {stats['total']}")
                
                dpg.add_spacer(height=4)
    
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
