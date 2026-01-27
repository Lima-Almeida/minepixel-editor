"""
Test script for Canvas Widget using Dear PyGui.
Run this to see the canvas in action with GPU acceleration.
"""

from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import numpy as np
import dearpygui.dearpygui as dpg
from PIL import Image

from app.ui.canvas_widget import CanvasWidget
from app.minecraft.texturepack.parser import TexturePackParser
from app.minecraft.texturepack.analyzer import TextureAnalyzer
from app.minecraft.texturepack.matcher import BlockMatcher
from app.minecraft.image_mapper import ImageToBlockMapper


class TestApp:
    def __init__(self):
        self.canvas = None
        self.blocks = []
        self.matcher = None  # BlockMatcher for image conversion
        self.status_text_tag = "status_text"
        self.sidebar_tag = "sidebar_window"
        self.block_stats_tag = "block_stats_group"
        
        # Known directional suffixes in Minecraft textures
        self.DIRECTIONAL_SUFFIXES = ['_top', '_side', '_front', '_back', '_bottom', '_end']
        
    def setup(self):
        dpg.create_context()
        
        # Create main window - full width for canvas
        with dpg.window(label="Canvas Test - Minecraft Pixel Art Editor (Dear PyGui)", 
                       tag="main_window", width=1200, height=850):
            
            # Controls
            with dpg.group(horizontal=True):
                dpg.add_button(label="Load Image", callback=self.open_file_dialog)
                dpg.add_button(label="Zoom In (+)", callback=lambda: self.canvas.zoom_in())
                dpg.add_button(label="Zoom Out (-)", callback=lambda: self.canvas.zoom_out())
                dpg.add_button(label="Fit to Window", callback=lambda: self.canvas.zoom_to_fit())
                dpg.add_button(label="Reset View", callback=lambda: self.canvas.reset_view())
                dpg.add_button(label="Toggle Grid", callback=self.toggle_grid)
            
            # Canvas
            self.canvas = CanvasWidget(tag="canvas", width=1180, height=750, parent="main_window")
            
            # Status
            dpg.add_text("Loading textures...", tag=self.status_text_tag)
        
        # Create floating sidebar window (overlay on the right)
        with dpg.window(label="Block Statistics", tag=self.sidebar_tag, 
                       width=360, height=820,
                       no_move=True, no_resize=False, no_collapse=True):
            dpg.add_text("Block Statistics")
            dpg.add_separator()
            dpg.add_text("Load an image to see statistics", tag="sidebar_placeholder")
            
            # Container for block stats (will be populated dynamically)
            with dpg.group(tag=self.block_stats_tag):
                pass
        
        # Setup canvas mouse handlers
        self.canvas.setup_handlers()
        
        # Load test data
        self.load_test_data()
        
        # Setup global handlers (mouse and keyboard)
        with dpg.handler_registry():
            # Keyboard
            dpg.add_key_press_handler(ord('+'), callback=lambda: self.canvas.zoom_in())
            dpg.add_key_press_handler(ord('='), callback=lambda: self.canvas.zoom_in())
            dpg.add_key_press_handler(ord('-'), callback=lambda: self.canvas.zoom_out())
            dpg.add_key_press_handler(ord('0'), callback=lambda: self.canvas.reset_view())
            dpg.add_key_press_handler(ord('F'), callback=lambda: self.canvas.zoom_to_fit())
            dpg.add_key_press_handler(ord('f'), callback=lambda: self.canvas.zoom_to_fit())
            dpg.add_key_press_handler(ord('G'), callback=self.toggle_grid)
            dpg.add_key_press_handler(ord('g'), callback=self.toggle_grid)
            
            # Mouse scroll for zoom
            dpg.add_mouse_wheel_handler(callback=self.on_mouse_scroll)
            
            # Mouse middle button for pan (press/release)
            dpg.add_mouse_down_handler(button=dpg.mvMouseButton_Middle, callback=self.on_pan_start)
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Middle, callback=self.on_pan_stop)
            
            # Global mouse move for pan (works even when mouse leaves canvas)
            dpg.add_mouse_move_handler(callback=self.on_mouse_move)
        
        dpg.create_viewport(title="Minecraft Pixel Art Editor Test", width=1580, height=870)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        
        # Position sidebar on the right side as overlay (after viewport is created)
        dpg.set_item_pos(self.sidebar_tag, [1210, 25])
    
    def toggle_grid(self):
        """Toggles grid visibility."""
        self.canvas.set_show_grid(not self.canvas.is_grid_visible())
    
    def get_base_block_name(self, block_id: str) -> str:
        """
        Gets the base name of a block by removing directional suffixes.
        Examples:
            - spruce_log_top -> spruce_log
            - grass_block_side -> grass_block
            - oak_planks -> oak_planks (no change)
        """
        for suffix in self.DIRECTIONAL_SUFFIXES:
            if block_id.endswith(suffix):
                return block_id[:-len(suffix)]
        return block_id
    
    def get_block_variant(self, block_id: str) -> str:
        """
        Gets the variant type of a block.
        Returns: 'normal', 'top', 'side', 'front', 'back', 'bottom', or 'end'
        """
        for suffix in self.DIRECTIONAL_SUFFIXES:
            if block_id.endswith(suffix):
                return suffix[1:]  # Remove leading underscore
        return 'normal'
    
    def analyze_grid_blocks(self) -> Dict[str, Dict]:
        """
        Analyzes the current grid and groups blocks by their base name.
        Returns a dict with block statistics including variant counts.
        
        Format:
        {
            'base_block_name': {
                'total': int,
                'variants': {
                    'normal': int,
                    'top': int,
                    'side': int,
                    ...
                },
                'blocks': [BlockTexture, ...]  # List of actual block objects
            }
        }
        """
        if not self.canvas or not self.canvas._grid:
            return {}
        
        # Count blocks by base name and variant
        block_counts = defaultdict(lambda: {
            'total': 0,
            'variants': defaultdict(int),
            'blocks': {}  # variant -> BlockTexture
        })
        
        for row in self.canvas._grid:
            for block in row:
                if block:
                    base_name = self.get_base_block_name(block.block_id)
                    variant = self.get_block_variant(block.block_id)
                    
                    block_counts[base_name]['total'] += 1
                    block_counts[base_name]['variants'][variant] += 1
                    
                    # Store one example of each variant
                    if variant not in block_counts[base_name]['blocks']:
                        block_counts[base_name]['blocks'][variant] = block
        
        return dict(block_counts)
    
    def update_sidebar_stats(self):
        """Updates the sidebar with current block statistics."""
        # Clear previous stats
        if dpg.does_item_exist(self.block_stats_tag):
            dpg.delete_item(self.block_stats_tag, children_only=True)
        
        # Analyze grid
        block_stats = self.analyze_grid_blocks()
        
        if not block_stats:
            dpg.add_text("No blocks in grid", parent=self.block_stats_tag)
            return
        
        # Calculate total blocks
        total_blocks = sum(stats['total'] for stats in block_stats.values())
        
        # Hide placeholder
        if dpg.does_item_exist("sidebar_placeholder"):
            dpg.hide_item("sidebar_placeholder")
        
        # Add total count
        dpg.add_text(f"Total Blocks: {total_blocks:,}", parent=self.block_stats_tag)
        dpg.add_text(f"Unique Types: {len(block_stats)}", parent=self.block_stats_tag)
        dpg.add_separator(parent=self.block_stats_tag)
        
        # Sort blocks by count (descending)
        sorted_blocks = sorted(block_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Create scrollable list of blocks
        with dpg.child_window(parent=self.block_stats_tag, height=650, width=320):
            for base_name, stats in sorted_blocks:
                with dpg.group():
                    # Get the first variant block for display
                    display_block = None
                    if 'normal' in stats['blocks']:
                        display_block = stats['blocks']['normal']
                    else:
                        # Use any available variant
                        display_block = next(iter(stats['blocks'].values()))
                    
                    # Create collapsing header for blocks with multiple variants
                    has_variants = len(stats['variants']) > 1
                    
                    if has_variants:
                        # Show texture and label inline with dropdown arrow
                        with dpg.group(horizontal=True):
                            # Show mini texture preview inline
                            if display_block and display_block.texture_path.exists():
                                self._add_mini_texture_preview(display_block)
                            
                            # Collapsing header with block name and count
                            with dpg.collapsing_header(label=f"{base_name}: {stats['total']} blocks",
                                                      default_open=False):
                                # Show variant breakdown inside dropdown
                                for variant, count in sorted(stats['variants'].items()):
                                    variant_block = stats['blocks'].get(variant)
                                    if variant_block:
                                        with dpg.group(horizontal=True):
                                            dpg.add_text(f"  • {variant.capitalize()}: {count}")
                                            # Show mini texture for each variant
                                            if variant_block.texture_path.exists():
                                                self._add_mini_texture_preview(variant_block)
                    else:
                        # Single variant - simple display
                        with dpg.group(horizontal=True):
                            if display_block and display_block.texture_path.exists():
                                self._add_mini_texture_preview(display_block)
                            dpg.add_text(f"{base_name}: {stats['total']}")
                    
                    with dpg.group():
                        dpg.add_spacer(height=4)
    
    def _add_texture_preview(self, block, parent=None):
        """Adds a texture preview image (32x32) to the UI."""
        try:
            texture_tag = f"preview_{block.block_id}"
            
            # Load texture if not already in registry
            if not dpg.does_item_exist(texture_tag):
                img = Image.open(block.texture_path).convert('RGBA')
                img = img.resize((32, 32), Image.Resampling.NEAREST)
                
                width, height = img.size
                # Use numpy array instead of deprecated getdata()
                img_array = np.array(img, dtype=np.float32) / 255.0
                img_data = img_array.flatten().tolist()
                
                with dpg.texture_registry():
                    dpg.add_static_texture(width=width, height=height, 
                                         default_value=img_data, tag=texture_tag)
            
            # Add image to UI
            if parent:
                dpg.add_image(texture_tag, parent=parent)
            else:
                dpg.add_image(texture_tag)
        except Exception as e:
            print(f"Error loading texture preview for {block.block_id}: {e}")
    
    def _add_mini_texture_preview(self, block):
        """Adds a mini texture preview (16x16) inline."""
        try:
            texture_tag = f"mini_{block.block_id}"
            
            # Load texture if not already in registry
            if not dpg.does_item_exist(texture_tag):
                img = Image.open(block.texture_path).convert('RGBA')
                img = img.resize((16, 16), Image.Resampling.NEAREST)
                
                width, height = img.size
                # Use numpy array instead of deprecated getdata()
                img_array = np.array(img, dtype=np.float32) / 255.0
                img_data = img_array.flatten().tolist()
                
                with dpg.texture_registry():
                    dpg.add_static_texture(width=width, height=height, 
                                         default_value=img_data, tag=texture_tag)
            
            dpg.add_image(texture_tag)
        except Exception as e:
            print(f"Error loading mini texture for {block.block_id}: {e}")
    
    def on_mouse_scroll(self, sender, app_data):
        """Handles mouse scroll for zooming."""
        if not dpg.is_item_hovered("canvas"):
            return
        
        # Get mouse position relative to canvas using the centralized method
        local_x, local_y = self.canvas._get_local_mouse_pos()
        
        # Zoom in or out
        if app_data > 0:
            self.canvas.set_zoom(self.canvas._zoom_level * 1.1, local_x, local_y)
        else:
            self.canvas.set_zoom(self.canvas._zoom_level / 1.1, local_x, local_y)
    
    def on_pan_start(self, sender, app_data):
        """Handles middle mouse button press to start panning."""
        # Only start pan if not already panning (prevent multiple calls)
        if self.canvas._is_panning:
            return
        
        if dpg.is_item_hovered("canvas"):
            self.canvas.start_pan()
    
    def on_pan_stop(self, sender, app_data):
        """Handles middle mouse button release to stop panning."""
        self.canvas.stop_pan()
    
    def on_mouse_move(self, sender, app_data):
        """Handles global mouse movement for pan updates."""
        if self.canvas and self.canvas._is_panning:
            self.canvas.update_pan()
            self.canvas.render()
    
    def load_test_data(self):
        """Loads test data with real Minecraft textures."""
        try:
            # Load textures
            texture_path = Path("assets/minecraft_textures/blocks")
            if not texture_path.exists():
                dpg.set_value(self.status_text_tag, 
                            "ERROR: Texture folder not found. Place textures in assets/minecraft_textures/blocks/")
                self.create_fallback_grid()
                return
            
            parser = TexturePackParser(texture_path)
            self.blocks = parser.parse()
            
            # Filter log_top textures (same as --ignore-log-tops in convert_image.py)
            original_count = len(self.blocks)
            self.blocks = [b for b in self.blocks if not b.block_id.endswith('_log_top')]
            filtered_count = original_count - len(self.blocks)
            if filtered_count > 0:
                print(f"[INFO] Filtered out {filtered_count} log_top textures")
            
            if not self.blocks:
                dpg.set_value(self.status_text_tag, 
                            "ERROR: No textures found. Add PNG files to assets/minecraft_textures/blocks/")
                self.create_fallback_grid()
                return
            
            # Analyze colors
            analyzer = TextureAnalyzer()
            analyzer.analyze(self.blocks)
            
            # Create matcher for image conversion
            self.matcher = BlockMatcher(self.blocks, allow_transparency=False)
            
            # Filter only solid blocks
            solid_blocks = [b for b in self.blocks if not b.has_transparency]
            
            if len(solid_blocks) < 10:
                solid_blocks = self.blocks  # Use all if not enough solid
            
            # Create a test grid with a pattern
            grid_width = 32
            grid_height = 24
            
            grid = []
            for y in range(grid_height):
                row = []
                for x in range(grid_width):
                    # Create a pattern using different blocks
                    block_index = (x + y) % len(solid_blocks)
                    row.append(solid_blocks[block_index])
                grid.append(row)
            
            # Set grid in canvas
            self.canvas.set_grid(grid)
            self.canvas.zoom_to_fit()
            
            # Set first block as current for painting
            if solid_blocks:
                self.canvas.set_current_block(solid_blocks[0])
            
            # Connect callbacks
            self.canvas.on_block_changed = self.on_block_changed
            self.canvas.on_selection_changed = self.on_selection_changed
            
            dpg.set_value(self.status_text_tag,
                f"Loaded {len(self.blocks)} textures | Grid: {grid_width}x{grid_height} | "
                f"Left Click: Paint | Middle Click: Pan | Scroll: Zoom"
            )
            
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.create_fallback_grid()
    
    def create_fallback_grid(self):
        """Creates a simple fallback grid for testing without textures."""
        from app.minecraft.texturepack.models import BlockTexture
        
        # Create some colored blocks manually
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
        ]
        
        blocks = []
        for i, color in enumerate(colors):
            # Create a dummy texture file in memory
            dummy_path = Path(f"dummy_{i}.png")
            block = BlockTexture(
                block_id=f"test_block_{i}",
                texture_path=dummy_path,
                avg_color=color,
                has_transparency=False
            )
            blocks.append(block)
        
        # Create test grid
        grid_width = 16
        grid_height = 12
        
        grid = []
        for y in range(grid_height):
            row = []
            for x in range(grid_width):
                block_index = (x + y) % len(blocks)
                row.append(blocks[block_index])
            grid.append(row)
        
        self.canvas.set_grid(grid)
        self.canvas.zoom_to_fit()
        
        if blocks:
            self.canvas.set_current_block(blocks[0])
        
        dpg.set_value(self.status_text_tag,
            f"FALLBACK MODE: Using colored blocks | "
            f"Left Click: Paint | Middle Click: Pan | Scroll: Zoom"
        )
    
    def on_block_changed(self, x, y, block):
        """Called when a block is changed."""
        info = self.canvas.get_canvas_info()
        dpg.set_value(self.status_text_tag,
            f"Block changed at ({x}, {y}) -> {block.block_id} | "
            f"Zoom: {info['zoom_level']:.1f}x | Grid: {info['grid_width']}x{info['grid_height']}"
        )
    
    def on_selection_changed(self, x, y):
        """Called when hover position changes."""
        if 0 <= x < self.canvas._grid_width and 0 <= y < self.canvas._grid_height:
            block = self.canvas.get_block_at(x, y)
            if block:
                info = self.canvas.get_canvas_info()
                dpg.set_value(self.status_text_tag,
                    f"Hover: ({x}, {y}) -> {block.block_id} | "
                    f"Zoom: {info['zoom_level']:.1f}x | "
                    f"Left Click: Paint | Middle Click: Pan | Scroll: Zoom"
                )
    
    def open_file_dialog(self):
        """Opens file dialog to select an image."""
        with dpg.file_dialog(
            directory_selector=False,
            show=True,
            callback=self.load_and_convert_image,
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
    
    def load_and_convert_image(self, sender, app_data):
        """Loads and converts selected image to Minecraft blocks."""
        selections = app_data.get('selections', {})
        if not selections:
            dpg.set_value(self.status_text_tag, "No file selected")
            return
        
        # Get the first selected file
        file_path = Path(list(selections.values())[0])
        
        if not file_path.exists():
            dpg.set_value(self.status_text_tag, f"ERROR: File not found: {file_path}")
            return
        
        dpg.set_value(self.status_text_tag, f"Loading image: {file_path.name}...")
        
        try:
            # Load image info
            with Image.open(file_path) as img:
                width, height = img.size
            
            dpg.set_value(self.status_text_tag, 
                f"Converting {file_path.name} ({width}x{height}) to blocks...")
            
            # Ensure matcher is created
            if self.matcher is None:
                if not self.blocks:
                    dpg.set_value(self.status_text_tag, "ERROR: No textures loaded")
                    return
                
                # Create matcher with solid blocks only
                self.matcher = BlockMatcher(self.blocks, allow_transparency=False)
            
            # Convert image to blocks
            mapper = ImageToBlockMapper(self.matcher)
            block_grid = mapper.map_image(file_path, target_size=None)
            
            # Load to canvas
            self.canvas.set_grid(block_grid)
            
            # Force a clean render before zoom
            self.canvas.render()
            
            # Zoom to fit the entire image
            self.canvas.zoom_to_fit()
            
            # Force another render after zoom
            self.canvas.render()
            
            # Update sidebar with block statistics
            self.update_sidebar_stats()
            
            # Set first block as current for painting
            if self.blocks:
                solid_blocks = [b for b in self.blocks if not b.has_transparency]
                if solid_blocks:
                    self.canvas.set_current_block(solid_blocks[0])
            
            grid_height = len(block_grid)
            grid_width = len(block_grid[0]) if grid_height > 0 else 0
            
            dpg.set_value(self.status_text_tag,
                f"Loaded {file_path.name} | Grid: {grid_width}x{grid_height} blocks | "
                f"Original: {width}x{height} px | Left Click: Paint | Middle Click: Pan | Scroll: Zoom"
            )
            
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        dpg.show_metrics()
        
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        
        dpg.destroy_context()


def main():
    app = TestApp()
    app.setup()
    app.run()


if __name__ == "__main__":
    main()
