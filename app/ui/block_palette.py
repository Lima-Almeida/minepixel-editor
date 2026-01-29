"""
Block Palette Widget - PySide6 version.
Visual block selector with search and thumbnails.
"""

from __future__ import annotations
from typing import List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QScrollArea, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QColor
from PIL import Image

from app.minecraft.texturepack.models import BlockTexture


class BlockPalette(QWidget):
    """Visual palette for selecting blocks (PySide6 version)."""
    
    # Signals
    block_selected = Signal(object)  # Emits BlockTexture
    
    def __init__(self, width: int = 280, height: int = 400):
        super().__init__()
        
        self._blocks: List[BlockTexture] = []
        self._selected_block: Optional[BlockTexture] = None
        self._texture_cache: dict[str, QPixmap] = {}
        self._search_filter: str = ""
        self._block_buttons: List[QPushButton] = []
        
        self.setMinimumSize(width, height)
        self.setMaximumWidth(width + 50)
        
        self._create_ui()
    
    def _create_ui(self):
        """Creates the palette UI."""
        layout = QVBoxLayout(self)
        
        # Search filter
        search_label = QLabel("Search:")
        layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter blocks...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)
        
        # Selected block display
        selected_layout = QHBoxLayout()
        selected_layout.addWidget(QLabel("Selected:"))
        self.selected_label = QLabel("None")
        self.selected_label.setWordWrap(True)
        selected_layout.addWidget(self.selected_label)
        selected_layout.addStretch()
        layout.addLayout(selected_layout)
        
        # Scrollable block list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.blocks_widget = QWidget()
        self.blocks_layout = QVBoxLayout(self.blocks_widget)
        self.blocks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.blocks_layout.setSpacing(2)
        
        scroll_area.setWidget(self.blocks_widget)
        layout.addWidget(scroll_area)
        
        self.setLayout(layout)
    
    def set_blocks(self, blocks: List[BlockTexture]):
        """Sets the available blocks."""
        self._blocks = blocks
        self._load_textures()
        self._update_block_list()
    
    def set_selected_block(self, block: Optional[BlockTexture]):
        """Sets the currently selected block."""
        self._selected_block = block
        self._update_selected_display()
        self._update_button_highlights()
    
    def get_selected_block(self) -> Optional[BlockTexture]:
        """Returns the currently selected block."""
        return self._selected_block
    
    def _on_search_changed(self, text: str):
        """Handles search filter changes."""
        self._search_filter = text.lower()
        self._update_block_list()
    
    def _load_textures(self):
        """Pre-loads block textures."""
        for block in self._blocks[:100]:  # Limit for performance
            if block.block_id not in self._texture_cache:
                self._load_texture(block)
    
    def _load_texture(self, block: BlockTexture) -> QPixmap:
        """Loads a block texture."""
        if block.block_id in self._texture_cache:
            return self._texture_cache[block.block_id]
        
        try:
            if block.texture_path.exists():
                pil_img = Image.open(block.texture_path).convert('RGBA')
                pil_img = pil_img.resize((24, 24), Image.Resampling.NEAREST)
                data = pil_img.tobytes("raw", "RGBA")
                qimage = QImage(data, 24, 24, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)
            else:
                color = block.avg_color if block.avg_color else (255, 0, 255)
                qimage = QImage(24, 24, QImage.Format.Format_RGBA8888)
                qimage.fill(QColor(*color))
                pixmap = QPixmap.fromImage(qimage)
        except Exception:
            color = block.avg_color if block.avg_color else (255, 0, 255)
            qimage = QImage(24, 24, QImage.Format.Format_RGBA8888)
            qimage.fill(QColor(*color))
            pixmap = QPixmap.fromImage(qimage)
        
        self._texture_cache[block.block_id] = pixmap
        return pixmap
    
    def _update_block_list(self):
        """Updates the displayed block list based on filter."""
        # Clear existing buttons
        while self.blocks_layout.count():
            child = self.blocks_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self._block_buttons.clear()
        
        # Filter blocks
        filtered_blocks = [
            b for b in self._blocks
            if not self._search_filter or self._search_filter in b.block_id.lower()
        ]
        
        # Create block buttons
        for block in filtered_blocks[:200]:  # Limit display
            self._create_block_button(block)
    
    def _create_block_button(self, block: BlockTexture):
        """Creates a button for a block."""
        # Ensure texture is loaded
        if block.block_id not in self._texture_cache:
            self._load_texture(block)
        
        pixmap = self._texture_cache.get(block.block_id)
        
        # Create button with horizontal layout
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(2, 2, 2, 2)
        button_layout.setSpacing(5)
        
        # Image button
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        if pixmap:
            btn.setIcon(pixmap)
            btn.setIconSize(QSize(24, 24))
        btn.clicked.connect(lambda checked, b=block: self._on_block_clicked(b))
        btn.setProperty("block_id", block.block_id)
        button_layout.addWidget(btn)
        
        # Block name label
        # Remove 'minecraft:' prefix for display
        display_name = block.block_id.replace('minecraft:', '')
        name_label = QLabel(display_name)
        name_label.setWordWrap(False)
        button_layout.addWidget(name_label)
        button_layout.addStretch()
        
        self.blocks_layout.addWidget(button_widget)
        self._block_buttons.append(btn)
    
    def _on_block_clicked(self, block: BlockTexture):
        """Handles block button click."""
        self.set_selected_block(block)
        self.block_selected.emit(block)
    
    def _update_selected_display(self):
        """Updates the selected block display."""
        if self._selected_block:
            self.selected_label.setText(self._selected_block.block_id)
        else:
            self.selected_label.setText("None")
    
    def _update_button_highlights(self):
        """Updates button highlights based on selection."""
        for btn in self._block_buttons:
            block_id = btn.property("block_id")
            if self._selected_block and block_id == self._selected_block.block_id:
                btn.setStyleSheet("background-color: #4080ff; border: 2px solid #60a0ff;")
            else:
                btn.setStyleSheet("")
