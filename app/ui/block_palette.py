"""
Block Palette Widget - Visual block selector.
"""

from __future__ import annotations
from typing import List, Optional, Callable
from pathlib import Path
import dearpygui.dearpygui as dpg
from PIL import Image
import numpy as np

from app.minecraft.texturepack.models import BlockTexture


class BlockPaletteWidget:
    """Visual palette for selecting blocks."""
    
    def __init__(self, tag: str, width: int = 280, height: int = 300, parent=None):
        """
        Initialize block palette widget.
        
        Args:
            tag: Unique tag for the widget
            width: Palette width
            height: Palette height
            parent: Parent container
        """
        self.tag = tag
        self.width = width
        self.height = height
        self.parent = parent
        
        self._blocks: List[BlockTexture] = []
        self._selected_block: Optional[BlockTexture] = None
        self._texture_cache: dict[str, str] = {}
        self._on_block_selected: Optional[Callable] = None
        
        # UI state
        self._search_filter = ""
        self._block_buttons = []
        
        # Create widget
        self._create_palette()
    
    def _create_palette(self) -> None:
        """Creates the palette UI."""
        with dpg.group(tag=self.tag, parent=self.parent):
            # Search filter
            dpg.add_text("Block Palette:")
            dpg.add_input_text(
                tag=f"{self.tag}_search",
                hint="Search blocks...",
                callback=self._on_search_changed,
                width=-1
            )
            dpg.add_separator()
            
            # Selected block display
            with dpg.group(tag=f"{self.tag}_selected_display", horizontal=True):
                dpg.add_text("Selected: ")
                dpg.add_text("None", tag=f"{self.tag}_selected_name")
            
            dpg.add_separator()
            
            # Scrollable block list
            with dpg.child_window(
                tag=f"{self.tag}_scroll",
                width=-1,
                height=self.height,
                border=True,
                horizontal_scrollbar=False,
                autosize_x=True
            ):
                dpg.add_group(tag=f"{self.tag}_blocks")
    
    def set_blocks(self, blocks: List[BlockTexture]) -> None:
        """
        Sets the available blocks.
        
        Args:
            blocks: List of BlockTexture objects
        """
        self._blocks = blocks
        self._load_textures()
        self._update_block_list()
    
    def set_selected_block(self, block: Optional[BlockTexture]) -> None:
        """
        Sets the currently selected block.
        
        Args:
            block: BlockTexture to select
        """
        self._selected_block = block
        self._update_selected_display()
        self._update_button_highlights()
    
    def get_selected_block(self) -> Optional[BlockTexture]:
        """Returns the currently selected block."""
        return self._selected_block
    
    def set_on_block_selected(self, callback: Callable) -> None:
        """
        Sets callback for block selection.
        
        Args:
            callback: Function(block) called when block is selected
        """
        self._on_block_selected = callback
    
    def _on_search_changed(self, sender, value):
        """Handles search filter changes."""
        self._search_filter = value.lower()
        self._update_block_list()
    
    def _load_textures(self) -> None:
        """Pre-loads block textures."""
        for block in self._blocks[:100]:  # Limit for performance
            if block.block_id not in self._texture_cache:
                self._load_texture(block)
    
    def _load_texture(self, block: BlockTexture) -> str:
        """Loads a block texture for DPG."""
        if block.block_id in self._texture_cache:
            return self._texture_cache[block.block_id]
        
        texture_tag = f"palette_{block.block_id}"
        
        try:
            if block.texture_path.exists():
                img = Image.open(block.texture_path).convert('RGBA')
                img = img.resize((24, 24), Image.NEAREST)
            else:
                color = block.avg_color if block.avg_color else (255, 0, 255)
                img = Image.new('RGBA', (24, 24), (*color, 255))
        except:
            color = block.avg_color if block.avg_color else (255, 0, 255)
            img = Image.new('RGBA', (24, 24), (*color, 255))
        
        # Convert to DPG format
        texture_data = np.frombuffer(img.tobytes(), dtype=np.uint8)
        texture_data = texture_data.reshape((img.height, img.width, 4))
        texture_data = texture_data.astype(np.float32) / 255.0
        
        if dpg.does_item_exist(texture_tag):
            dpg.delete_item(texture_tag)
        
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
    
    def _update_block_list(self) -> None:
        """Updates the displayed block list based on filter."""
        # Clear existing buttons
        if dpg.does_item_exist(f"{self.tag}_blocks"):
            dpg.delete_item(f"{self.tag}_blocks", children_only=True)
        
        self._block_buttons = []
        
        # Filter blocks
        filtered_blocks = [
            b for b in self._blocks
            if not self._search_filter or self._search_filter in b.block_id.lower()
        ]
        
        # Create block buttons directly in the blocks group
        for block in filtered_blocks[:200]:  # Limit display
            self._create_block_button(block)
    
    def _create_block_button(self, block: BlockTexture) -> None:
        """Creates a button for a block."""
        button_tag = f"{self.tag}_btn_{block.block_id}"
        
        # Ensure texture is loaded
        if block.block_id not in self._texture_cache:
            self._load_texture(block)
        
        texture_tag = self._texture_cache.get(block.block_id)
        
        with dpg.group(horizontal=True, parent=f"{self.tag}_blocks"):
            # Image button
            if texture_tag:
                dpg.add_image_button(
                    texture_tag,
                    tag=button_tag,
                    width=24,
                    height=24,
                    callback=lambda s, a, u: self._on_block_clicked(u),
                    user_data=block
                )
            else:
                dpg.add_button(
                    label=" ",
                    tag=button_tag,
                    width=24,
                    height=24,
                    callback=lambda s, a, u: self._on_block_clicked(u),
                    user_data=block
                )
            
            # Block name
            dpg.add_text(block.block_id)
        
        self._block_buttons.append((button_tag, block))
    
    def _on_block_clicked(self, block: BlockTexture) -> None:
        """Handles block button click."""
        self.set_selected_block(block)
        if self._on_block_selected:
            self._on_block_selected(block)
    
    def _update_selected_display(self) -> None:
        """Updates the selected block display."""
        if self._selected_block:
            dpg.set_value(f"{self.tag}_selected_name", self._selected_block.block_id)
        else:
            dpg.set_value(f"{self.tag}_selected_name", "None")
    
    def _update_button_highlights(self) -> None:
        """Updates button highlights based on selection."""
        # Note: DPG doesn't have easy way to highlight buttons
        # Could add colored border or text indicator in future
        pass
