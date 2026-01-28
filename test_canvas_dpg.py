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
from app.minecraft.texturepack.utils import load_ignored_textures


class TestApp:
    def __init__(self):
        self.canvas = None
        self.blocks = []
        self.all_blocks = []  # All blocks including ignored ones
        self.matcher = None  # BlockMatcher for image conversion
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
        self.last_loaded_image = None  # Store last loaded image path for re-rendering
        
        # Load ignored textures from file
        self.default_ignored_blocks = load_ignored_textures()  # Set of ignored base names from file
        self.user_ignored_blocks = set()  # User-selected ignored blocks (will be initialized later)
        self._settings_initialized = False  # Flag to know if we've initialized user settings
        
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
                dpg.add_button(label="Export Image", callback=self.open_export_image_dialog)
                dpg.add_button(label="Settings", callback=self.open_settings_modal)
                dpg.add_button(label="Zoom In (+)", callback=lambda: self.canvas.zoom_in())
                dpg.add_button(label="Zoom Out (-)", callback=lambda: self.canvas.zoom_out())
                dpg.add_button(label="Fit to Window", callback=lambda: self.canvas.zoom_to_fit())
                dpg.add_button(label="Reset View", callback=lambda: self.canvas.reset_view())
                dpg.add_button(label="Toggle Grid", callback=self.toggle_grid)
            
            # Canvas
            self.canvas = CanvasWidget(tag="canvas", width=1180, height=750, parent="main_window")
            
            # Status bar with progress
            with dpg.group(horizontal=True, tag=self.status_group_tag):
                dpg.add_text("Loading textures...", tag=self.status_text_tag)
                dpg.add_spacer(width=20)
                dpg.add_progress_bar(tag=self.progress_bar_tag, default_value=0.0, 
                                   width=200, show=False)
        
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
            
            # Export button at the bottom
            dpg.add_separator()
            dpg.add_button(label="Export Block List to TXT", callback=self.open_export_dialog,
                         width=-1, height=30)
        
        # Setup canvas mouse handlers
        self.canvas.setup_handlers()
        
        # Load test data
        self.load_test_data()
        
        # Pre-load all block textures for modal (done once for performance)
        self.preload_block_textures()
        
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
    
    def is_block_ignored(self, base_name: str) -> bool:
        """Check if a block base name is ignored."""
        return base_name in self.user_ignored_blocks
    
    def preload_block_textures(self):
        """Pre-loads all block textures to registry for fast modal display."""
        if not self.all_blocks:
            return
        
        print("[DEBUG] Pre-loading block textures for modal...")
        loaded_count = 0
        
        for block in self.all_blocks:
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
                        loaded_count += 1
                except Exception:
                    pass  # Skip problematic textures
        
        print(f"[DEBUG] Pre-loaded {loaded_count} textures")
    
    def show_progress(self, progress: float = 0.0):
        """Shows and updates the progress bar."""
        if dpg.does_item_exist(self.progress_bar_tag):
            dpg.set_value(self.progress_bar_tag, progress)
            dpg.show_item(self.progress_bar_tag)
    
    def hide_progress(self):
        """Hides the progress bar."""
        if dpg.does_item_exist(self.progress_bar_tag):
            dpg.hide_item(self.progress_bar_tag)
    
    def open_settings_modal(self):
        """Opens the settings modal for managing ignored blocks."""
        # Create modal if it doesn't exist
        if not dpg.does_item_exist(self.settings_modal_tag):
            with dpg.window(label="Block Settings", tag=self.settings_modal_tag,
                          modal=True, show=False, width=600, height=750,
                          pos=[460, 85]):
                dpg.add_text("Manage blocks used in conversions:")
                dpg.add_separator()
                
                with dpg.group(tag=self.settings_content_tag):
                    pass
                
                dpg.add_separator()
                
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Apply & Re-render", callback=self.apply_settings_and_rerender,
                                 width=150, height=30)
                    dpg.add_button(label="Reset to Default", callback=self.reset_to_default_blocks,
                                 width=150, height=30)
                    dpg.add_button(label="Close", callback=lambda: dpg.hide_item(self.settings_modal_tag),
                                 width=100, height=30)
        
        # Populate with current blocks
        self.populate_settings_modal()
        
        # Show modal
        dpg.show_item(self.settings_modal_tag)
    
    def _initialize_user_ignored_blocks(self):
        """Initialize user_ignored_blocks with default ignored textures and transparent blocks."""
        if not self.all_blocks:
            print("[WARNING] Cannot initialize ignored blocks - no blocks loaded yet")
            return
        
        # Group blocks to get base names and their variants
        all_base_names = set()
        base_to_variants = defaultdict(set)  # base_name -> set of full texture names
        base_to_blocks = defaultdict(list)  # base_name -> list of BlockTexture objects
        
        for block in self.all_blocks:
            base_name = self.get_base_block_name(block.block_id)
            all_base_names.add(base_name)
            # Store the texture name without "minecraft:" prefix
            texture_name = block.block_id.split(':')[-1] if ':' in block.block_id else block.block_id
            base_to_variants[base_name].add(texture_name)
            base_to_blocks[base_name].append(block)
        
        print(f"[DEBUG] Found {len(all_base_names)} unique base names in loaded blocks")
        print(f"[DEBUG] Default ignored list has {len(self.default_ignored_blocks)} entries")
        
        # Add default ignored blocks
        # Strategy: if ANY variant of a block is in the ignore list, ignore the whole block
        matched_count = 0
        transparency_count = 0
        
        for base_name in all_base_names:
            # Check if base name (without prefix) matches
            name_without_prefix = base_name.split(':')[-1] if ':' in base_name else base_name
            
            # Check if base name itself is in ignored list
            if name_without_prefix in self.default_ignored_blocks:
                self.user_ignored_blocks.add(base_name)
                matched_count += 1
                continue
            
            # Check if ANY of the variants are in ignored list
            variants = base_to_variants[base_name]
            variant_matched = False
            for variant in variants:
                if variant in self.default_ignored_blocks:
                    self.user_ignored_blocks.add(base_name)
                    matched_count += 1
                    variant_matched = True
                    break  # Only count once per base name
            
            # Skip transparency check if already matched
            if variant_matched:
                continue
            
            # Check if ANY variant has transparency
            blocks_for_base = base_to_blocks[base_name]
            for block in blocks_for_base:
                if block.has_transparency:
                    self.user_ignored_blocks.add(base_name)
                    transparency_count += 1
                    break  # Only count once per base name
        
        print(f"[INFO] Initialized with {len(self.user_ignored_blocks)} default ignored blocks:")
        print(f"       - {matched_count} matched from ignored_textures.txt")
        print(f"       - {transparency_count} blocks with transparency")
        
        # Show some examples for debugging
        if self.user_ignored_blocks:
            examples = list(self.user_ignored_blocks)[:10]
            print(f"[DEBUG] Example ignored blocks: {examples}")
        else:
            print("[WARNING] No ignored blocks were matched!")
    
    def populate_settings_modal(self):
        """Populates the settings modal with two separate lists (active and ignored)."""
        # Clear previous content
        if dpg.does_item_exist(self.settings_content_tag):
            dpg.delete_item(self.settings_content_tag, children_only=True)
        
        if not self.all_blocks:
            dpg.add_text("No blocks loaded", parent=self.settings_content_tag)
            return
        
        # Group blocks by base name (cache this result)
        if not hasattr(self, '_grouped_blocks_cache'):
            print("[DEBUG] Building grouped blocks cache...")
            self._grouped_blocks_cache = defaultdict(lambda: {'variants': [], 'blocks': {}})
            for block in self.all_blocks:
                base_name = self.get_base_block_name(block.block_id)
                variant = self.get_block_variant(block.block_id)
                self._grouped_blocks_cache[base_name]['variants'].append(variant)
                self._grouped_blocks_cache[base_name]['blocks'][variant] = block
            print(f"[DEBUG] Cache built with {len(self._grouped_blocks_cache)} base blocks")
        
        grouped_blocks = self._grouped_blocks_cache
        
        # Separate into active and ignored
        self._active_blocks_list = []
        self._ignored_blocks_list = []
        
        for base_name, data in sorted(grouped_blocks.items()):
            is_ignored = self.is_block_ignored(base_name)
            if is_ignored:
                self._ignored_blocks_list.append((base_name, data))
            else:
                self._active_blocks_list.append((base_name, data))
        
        print(f"[DEBUG] Active blocks: {len(self._active_blocks_list)}, Ignored blocks: {len(self._ignored_blocks_list)}")
        
        # Active blocks list (top) - limit initial display for performance
        dpg.add_text(f"Active Blocks ({len(self._active_blocks_list)})", parent=self.settings_content_tag)
        dpg.add_input_text(tag=self.active_search_tag, parent=self.settings_content_tag,
                          hint="Search active blocks...", width=570,
                          callback=lambda: self.filter_settings_lists())
        with dpg.child_window(parent=self.settings_content_tag, height=220, width=570,
                            tag="active_blocks_list"):
            # Use table for better performance
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp,
                         borders_innerV=False, borders_outerV=False,
                         borders_innerH=False, borders_outerH=False):
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.8)
                
                # Only show first 150 items initially for performance
                display_count = min(150, len(self._active_blocks_list))
                for base_name, data in self._active_blocks_list[:display_count]:
                    self._create_block_item_table(base_name, data, is_ignored=False)
            
            # Show message if there are more
            if len(self._active_blocks_list) > display_count:
                dpg.add_text(f"... and {len(self._active_blocks_list) - display_count} more. Use search to filter.")
        
        dpg.add_spacer(height=10, parent=self.settings_content_tag)
        
        # Ignored blocks list (bottom) - limit initial display for performance
        dpg.add_text(f"Ignored Blocks ({len(self._ignored_blocks_list)})", parent=self.settings_content_tag)
        dpg.add_input_text(tag=self.ignored_search_tag, parent=self.settings_content_tag,
                          hint="Search ignored blocks...", width=570,
                          callback=lambda: self.filter_settings_lists())
        with dpg.child_window(parent=self.settings_content_tag, height=220, width=570,
                            tag="ignored_blocks_list"):
            # Use table for better performance
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp,
                         borders_innerV=False, borders_outerV=False,
                         borders_innerH=False, borders_outerH=False):
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.8)
                
                # Only show first 150 items initially for performance
                display_count = min(150, len(self._ignored_blocks_list))
                for base_name, data in self._ignored_blocks_list[:display_count]:
                    self._create_block_item_table(base_name, data, is_ignored=True)
            
            # Show message if there are more
            if len(self._ignored_blocks_list) > display_count:
                dpg.add_text(f"... and {len(self._ignored_blocks_list) - display_count} more. Use search to filter.")
    
    def filter_settings_lists(self):
        """Filters the settings lists based on search queries without recreating the entire modal."""
        # Get search queries
        active_query = dpg.get_value(self.active_search_tag).lower() if dpg.does_item_exist(self.active_search_tag) else ""
        ignored_query = dpg.get_value(self.ignored_search_tag).lower() if dpg.does_item_exist(self.ignored_search_tag) else ""
        
        # Clear and repopulate active blocks list (limit to 150 results)
        if dpg.does_item_exist("active_blocks_list"):
            dpg.delete_item("active_blocks_list", children_only=True)
            
            # Create new table
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp,
                         borders_innerV=False, borders_outerV=False,
                         borders_innerH=False, borders_outerH=False,
                         parent="active_blocks_list"):
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.8)
                
                count = 0
                max_display = 150
                for base_name, data in self._active_blocks_list:
                    if not active_query or active_query in base_name.lower():
                        if count < max_display:
                            self._create_block_item_table(base_name, data, is_ignored=False)
                            count += 1
                        else:
                            break
            
            # Show truncation message if needed
            if count >= max_display:
                dpg.add_text(f"... showing first {max_display} results. Refine your search.", 
                           parent="active_blocks_list")
        
        # Clear and repopulate ignored blocks list (limit to 150 results)
        if dpg.does_item_exist("ignored_blocks_list"):
            dpg.delete_item("ignored_blocks_list", children_only=True)
            
            # Create new table
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp,
                         borders_innerV=False, borders_outerV=False,
                         borders_innerH=False, borders_outerH=False,
                         parent="ignored_blocks_list"):
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.1)
                dpg.add_table_column(init_width_or_weight=0.8)
                
                count = 0
                max_display = 150
                for base_name, data in self._ignored_blocks_list:
                    if not ignored_query or ignored_query in base_name.lower():
                        if count < max_display:
                            self._create_block_item_table(base_name, data, is_ignored=True)
                            count += 1
                        else:
                            break
            
            # Show truncation message if needed
            if count >= max_display:
                dpg.add_text(f"... showing first {max_display} results. Refine your search.", 
                           parent="ignored_blocks_list")
    
    def _create_block_item_table(self, base_name: str, data: dict, is_ignored: bool):
        """Creates a block item as table row (much faster than groups)."""
        display_block = data['blocks'].get('normal') or next(iter(data['blocks'].values()))
        
        with dpg.table_row():
            # Checkbox column
            with dpg.table_cell():
                checkbox_tag = f"ignore_checkbox_{base_name}"
                dpg.add_checkbox(default_value=is_ignored, tag=checkbox_tag,
                               callback=lambda s, a, u: self.toggle_block_ignore(u, a),
                               user_data=base_name)
            
            # Texture column
            with dpg.table_cell():
                if display_block:
                    texture_tag = f"mini_{display_block.block_id}"
                    if dpg.does_item_exist(texture_tag):
                        dpg.add_image(texture_tag)
            
            # Name column
            with dpg.table_cell():
                variant_count = len(data['variants'])
                if variant_count > 1:
                    label = f"{base_name} ({variant_count} variants)"
                else:
                    label = base_name
                dpg.add_text(label)
    
    def _create_block_item(self, base_name: str, data: dict, is_ignored: bool, parent=None):
        """Creates a block item UI element with texture preview."""
        # Get display block (prefer 'normal' variant)
        display_block = data['blocks'].get('normal') or next(iter(data['blocks'].values()))
        
        # Create group with or without explicit parent
        group_kwargs = {'horizontal': True}
        if parent is not None:
            group_kwargs['parent'] = parent
        
        with dpg.group(**group_kwargs):
            # Checkbox for ignoring
            checkbox_tag = f"ignore_checkbox_{base_name}"
            dpg.add_checkbox(default_value=is_ignored, tag=checkbox_tag,
                           callback=lambda s, a, u: self.toggle_block_ignore(u, a),
                           user_data=base_name)
            
            # Mini texture preview (use cached version if exists)
            if display_block and display_block.texture_path.exists():
                texture_tag = f"mini_{display_block.block_id}"
                # Only create if doesn't exist yet
                if not dpg.does_item_exist(texture_tag):
                    self._add_mini_texture_preview(display_block)
                else:
                    # Just add reference to existing texture
                    dpg.add_image(texture_tag)
            
            # Block name (simplified - no collapsing headers for performance)
            variant_count = len(data['variants'])
            if variant_count > 1:
                label = f"{base_name} ({variant_count} variants)"
            else:
                label = base_name
            
            dpg.add_text(label)
    
    def toggle_block_ignore(self, base_name: str, is_checked: bool):
        """Toggle ignore state for a block."""
        if is_checked:
            self.user_ignored_blocks.add(base_name)
        else:
            self.user_ignored_blocks.discard(base_name)
    
    def toggle_block_ignore_with_refresh(self, base_name: str, is_checked: bool):
        """Toggle ignore state and refresh the modal to move blocks between lists."""
        self.toggle_block_ignore(base_name, is_checked)
        # Refresh the modal to reorganize blocks
        self.populate_settings_modal()
    
    def reset_to_default_blocks(self):
        """Resets ignored blocks to default state (only ignored_textures.txt)."""
        # Reset to defaults
        self.user_ignored_blocks.clear()
        self._initialize_user_ignored_blocks()
        # Refresh modal
        self.populate_settings_modal()
        dpg.set_value(self.status_text_tag, "Block filters reset to default")
    
    def apply_settings_and_rerender(self):
        """Apply ignore settings and re-render the current image."""
        # Hide modal
        dpg.hide_item(self.settings_modal_tag)
        
        # Reload blocks with new ignore settings
        self.reload_blocks_with_filters()
        
        # Re-render image if one is loaded
        if self.last_loaded_image:
            dpg.set_value(self.status_text_tag, "Re-rendering with new block settings...")
            self.convert_and_load_image(self.last_loaded_image)
        else:
            dpg.set_value(self.status_text_tag, "Block filters updated. Load an image to see changes.")
    
    def reload_blocks_with_filters(self):
        """Reloads blocks applying current ignore filters."""
        try:
            texture_path = Path("assets/minecraft_textures/blocks")
            if not texture_path.exists():
                return
            
            # Parse all blocks (no filtering - we handle filtering in _initialize_user_ignored_blocks)
            parser = TexturePackParser(texture_path)
            self.all_blocks = parser.parse(ignore_non_blocks=False)  # Load ALL blocks
            
            # Filter log_top textures
            original_count = len(self.all_blocks)
            self.all_blocks = [b for b in self.all_blocks if not b.block_id.endswith('_log_top')]
            log_top_filtered = original_count - len(self.all_blocks)
            if log_top_filtered > 0:
                print(f"[DEBUG] Filtered {log_top_filtered} log_top textures")
            
            # CRITICAL: Analyze textures for transparency BEFORE initializing ignored blocks
            print("[DEBUG] Analyzing textures for transparency...")
            analyzer = TextureAnalyzer(transparency_threshold=0.05)
            analyzer.analyze(self.all_blocks)
            transparent_count = sum(1 for b in self.all_blocks if b.has_transparency)
            print(f"[DEBUG] Found {transparent_count} blocks with transparency out of {len(self.all_blocks)}")
            
            # Initialize user_ignored_blocks with defaults on first load
            if not self._settings_initialized:
                self._initialize_user_ignored_blocks()
                self._settings_initialized = True
            
            # Filter user-ignored blocks (by base name)
            self.blocks = []
            for block in self.all_blocks:
                base_name = self.get_base_block_name(block.block_id)
                if base_name not in self.user_ignored_blocks:
                    self.blocks.append(block)
            
            print(f"[INFO] Loaded {len(self.all_blocks)} total blocks")
            print(f"[INFO] Using {len(self.blocks)} blocks after filters")
            print(f"[INFO] Ignored {len(self.all_blocks) - len(self.blocks)} blocks")
            
            # Re-analyze colors for filtered blocks (transparency already analyzed above)
            # Note: analyzer will skip transparency re-calculation since it's already set
            if self.blocks:
                # Recreate matcher (will filter out transparent blocks automatically)
                self.matcher = BlockMatcher(self.blocks, allow_transparency=False)
        
        except Exception as e:
            print(f"Error reloading blocks: {e}")
            import traceback
            traceback.print_exc()
    
    def convert_and_load_image(self, file_path: Path):
        """Converts and loads an image to the canvas."""
        try:
            # Load image info
            with Image.open(file_path) as img:
                width, height = img.size
            
            dpg.set_value(self.status_text_tag, 
                f"Converting {file_path.name} ({width}x{height}) to blocks...")
            self.show_progress(0.0)
            
            # Ensure matcher is created
            if self.matcher is None:
                if not self.blocks:
                    dpg.set_value(self.status_text_tag, "ERROR: No textures loaded")
                    self.hide_progress()
                    return
                
                # Create matcher with solid blocks only
                self.matcher = BlockMatcher(self.blocks, allow_transparency=False)
            
            # Convert image to blocks with progress callback
            mapper = ImageToBlockMapper(self.matcher)
            
            def update_progress(progress):
                self.show_progress(progress)
            
            block_grid = mapper.map_image(file_path, target_size=None, progress_callback=update_progress)
            
            # Show rendering progress
            dpg.set_value(self.status_text_tag, f"Rendering {file_path.name}...")
            self.show_progress(0.9)
            
            # Load to canvas
            self.canvas.set_grid(block_grid)
            
            # Force a clean render before zoom
            self.canvas.render()
            
            self.show_progress(0.95)
            
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
            
            self.show_progress(1.0)
            dpg.set_value(self.status_text_tag,
                f"Loaded {file_path.name} | Grid: {grid_width}x{grid_height} blocks | "
                f"Original: {width}x{height} px | Left Click: Paint | Middle Click: Pan | Scroll: Zoom"
            )
            
            # Hide progress after a brief moment
            self.hide_progress()
            
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR: {e}")
            self.hide_progress()
            import traceback
            traceback.print_exc()
    
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
    
    def open_export_dialog(self):
        """Opens file dialog to export block statistics."""
        # Check if there are statistics to export
        block_stats = self.analyze_grid_blocks()
        if not block_stats:
            dpg.set_value(self.status_text_tag, "No blocks to export. Load an image first.")
            return
        
        # Create file dialog if it doesn't exist
        if not dpg.does_item_exist(self.export_dialog_tag):
            with dpg.file_dialog(directory_selector=False, show=False, 
                               callback=self.export_block_list,
                               tag=self.export_dialog_tag,
                               width=700, height=400,
                               default_filename="block_list.txt"):
                dpg.add_file_extension(".txt", color=(150, 255, 150, 255))
        
        dpg.show_item(self.export_dialog_tag)
    
    def export_block_list(self, sender, app_data):
        """Exports block statistics to a text file."""
        try:
            # Get selected file path
            file_path = Path(app_data['file_path_name'])
            
            # Ensure .txt extension
            if file_path.suffix.lower() != '.txt':
                file_path = file_path.with_suffix('.txt')
            
            # Get block statistics
            block_stats = self.analyze_grid_blocks()
            if not block_stats:
                dpg.set_value(self.status_text_tag, "No blocks to export")
                return
            
            # Calculate totals
            total_blocks = sum(stats['total'] for stats in block_stats.values())
            unique_types = len(block_stats)
            
            # Generate text content
            lines = []
            lines.append("="*60)
            lines.append("MINECRAFT PIXEL ART - BLOCK LIST")
            lines.append("="*60)
            lines.append("")
            lines.append(f"Total Blocks: {total_blocks:,}")
            lines.append(f"Unique Types: {unique_types}")
            lines.append("")
            lines.append("="*60)
            lines.append("BLOCKS BY QUANTITY (Most to Least)")
            lines.append("="*60)
            lines.append("")
            
            # Sort blocks by count (descending)
            sorted_blocks = sorted(block_stats.items(), key=lambda x: x[1]['total'], reverse=True)
            
            for base_name, stats in sorted_blocks:
                # Main block line
                lines.append(f"{base_name}: {stats['total']} blocks")
                
                # If multiple variants, show breakdown
                if len(stats['variants']) > 1:
                    for variant, count in sorted(stats['variants'].items(), key=lambda x: x[1], reverse=True):
                        lines.append(f"  • {variant}: {count}")
                    lines.append("")  # Empty line after multi-variant blocks
            
            lines.append("")
            lines.append("="*60)
            lines.append("Generated by Minepixel Editor")
            lines.append("="*60)
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            dpg.set_value(self.status_text_tag, f"Block list exported to: {file_path.name}")
            
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR exporting: {e}")
            import traceback
            traceback.print_exc()
    
    def open_export_image_dialog(self):
        """Opens file dialog to export canvas image as PNG."""
        # Check if there's an image loaded
        if not self.canvas or not self.canvas._grid:
            dpg.set_value(self.status_text_tag, "No image to export. Load an image first.")
            return
        
        # Create file dialog if it doesn't exist
        if not dpg.does_item_exist(self.export_image_dialog_tag):
            with dpg.file_dialog(directory_selector=False, show=False, 
                               callback=self.export_canvas_image,
                               tag=self.export_image_dialog_tag,
                               width=700, height=400,
                               default_filename="minecraft_art.png"):
                dpg.add_file_extension(".png", color=(150, 255, 150, 255))
        
        dpg.show_item(self.export_image_dialog_tag)
    
    def export_canvas_image(self, sender, app_data):
        """Exports the canvas grid as a PNG image."""
        try:
            # Get selected file path
            file_path = Path(app_data['file_path_name'])
            
            # Ensure .png extension
            if file_path.suffix.lower() != '.png':
                file_path = file_path.with_suffix('.png')
            
            # Check if grid exists
            if not self.canvas or not self.canvas._grid:
                dpg.set_value(self.status_text_tag, "No image to export")
                return
            
            # Show progress
            dpg.set_value(self.status_text_tag, f"Exporting image to {file_path.name}...")
            self.show_progress(0.1)
            
            # Get the block grid from canvas
            block_grid = self.canvas._grid
            
            # Calculate dimensions
            grid_height = len(block_grid)
            grid_width = len(block_grid[0]) if grid_height > 0 else 0
            
            self.show_progress(0.3)
            
            # Use BlockRenderer to render the image
            from app.core.renderer import BlockRenderer
            renderer = BlockRenderer(block_size=16)
            
            self.show_progress(0.5)
            
            # Render and save
            rendered_image = renderer.render(block_grid, output_path=file_path)
            
            self.show_progress(1.0)
            
            dpg.set_value(self.status_text_tag, 
                f"Image exported: {file_path.name} ({grid_width}x{grid_height} blocks)")
            
            # Hide progress
            self.hide_progress()
            
        except Exception as e:
            dpg.set_value(self.status_text_tag, f"ERROR exporting image: {e}")
            self.hide_progress()
            import traceback
            traceback.print_exc()
    
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
            # Load textures using the new reload system
            self.reload_blocks_with_filters()
            
            if not self.blocks:
                dpg.set_value(self.status_text_tag, 
                            "ERROR: No textures found. Add PNG files to assets/minecraft_textures/blocks/")
                self.create_fallback_grid()
                return
            
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
        
        # Store for re-rendering
        self.last_loaded_image = file_path
        
        # Convert and load
        self.convert_and_load_image(file_path)
    
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
