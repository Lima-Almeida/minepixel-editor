"""
Settings Dialog - PySide6 version
Manages block ignore list and application settings.
"""

from __future__ import annotations
from typing import Set, List, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QCheckBox, QGroupBox,
    QScrollArea, QWidget, QFrame, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from app.minecraft.texturepack.models import BlockTexture


class SettingsDialog(QDialog):
    """Dialog for managing application settings."""
    
    settings_changed = Signal()
    re_render_requested = Signal()
    
    def __init__(self, block_manager, parent=None):
        super().__init__(parent)
        self.block_manager = block_manager
        self.setWindowTitle("Settings - Minepixel Editor")
        self.setModal(True)
        self.resize(900, 600)
        
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self):
        """Setup UI layout."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("<h2>Settings</h2>")
        layout.addWidget(title)
        
        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self._update_statistics()
        layout.addWidget(self.stats_label)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter blocks...")
        self.search_input.textChanged.connect(self._filter_blocks)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Splitter with two lists
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Active blocks list
        active_widget = QWidget()
        active_layout = QVBoxLayout(active_widget)
        active_layout.setContentsMargins(0, 0, 0, 0)
        
        active_label = QLabel("<b>Active Blocks</b>")
        active_layout.addWidget(active_label)
        
        self.active_list = QListWidget()
        self.active_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        active_layout.addWidget(self.active_list)
        
        # Button to move to ignored
        move_to_ignored_btn = QPushButton("→ Ignore Selected")
        move_to_ignored_btn.clicked.connect(self._move_to_ignored)
        active_layout.addWidget(move_to_ignored_btn)
        
        splitter.addWidget(active_widget)
        
        # Ignored blocks list
        ignored_widget = QWidget()
        ignored_layout = QVBoxLayout(ignored_widget)
        ignored_layout.setContentsMargins(0, 0, 0, 0)
        
        ignored_label = QLabel("<b>Ignored Blocks</b>")
        ignored_layout.addWidget(ignored_label)
        
        self.ignored_list = QListWidget()
        self.ignored_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        ignored_layout.addWidget(self.ignored_list)
        
        # Button to move to active
        move_to_active_btn = QPushButton("← Activate Selected")
        move_to_active_btn.clicked.connect(self._move_to_active)
        ignored_layout.addWidget(move_to_active_btn)
        
        splitter.addWidget(ignored_widget)
        
        layout.addWidget(splitter)
        
        # Bulk actions
        bulk_layout = QHBoxLayout()
        
        activate_all_btn = QPushButton("Activate All")
        activate_all_btn.clicked.connect(self._activate_all)
        bulk_layout.addWidget(activate_all_btn)
        
        ignore_all_btn = QPushButton("Ignore All")
        ignore_all_btn.clicked.connect(self._ignore_all)
        bulk_layout.addWidget(ignore_all_btn)
        
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_to_default)
        bulk_layout.addWidget(reset_btn)
        
        bulk_layout.addStretch()
        layout.addLayout(bulk_layout)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save && Apply")
        save_btn.clicked.connect(self._save_and_apply)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        self._populate_lists()
    
    def _load_current_settings(self):
        """Load current settings from block manager."""
        pass  # Already loaded in _populate_lists
    
    def _update_statistics(self):
        """Update statistics display."""
        total = len(self.block_manager.all_blocks) if self.block_manager else 0
        active = len(self.block_manager.active_blocks) if self.block_manager else 0
        ignored = total - active
        self.stats_label.setText(
            f"<b>Total Blocks:</b> {total} | "
            f"<b>Active:</b> {active} | "
            f"<b>Ignored:</b> {ignored}"
        )
    
    def _populate_lists(self):
        """Populate both lists with blocks."""
        if not self.block_manager or not self.block_manager.all_blocks:
            return
        
        # Group blocks by base name
        from collections import defaultdict
        from app.core.block_manager import BlockManager
        
        base_to_blocks = defaultdict(list)
        for block in self.block_manager.all_blocks:
            base_name = BlockManager.get_base_block_name(block.block_id)
            base_to_blocks[base_name].append(block)
        
        # Sort base names
        sorted_bases = sorted(base_to_blocks.keys())
        
        # Clear lists
        self.active_list.clear()
        self.ignored_list.clear()
        
        # Populate lists
        for base_name in sorted_bases:
            blocks = base_to_blocks[base_name]
            display_block = blocks[0]
            
            # Check if ignored
            is_ignored = base_name in self.block_manager.user_ignored_blocks
            
            # Create display name with variant count
            display_name = base_name.replace('minecraft:', '')
            if len(blocks) > 1:
                display_name += f" ({len(blocks)} variants)"
            
            # Create list item
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, base_name)
            
            # Add thumbnail
            if display_block.texture_path.exists():
                try:
                    pixmap = QPixmap(str(display_block.texture_path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, 
                                             Qt.TransformationMode.FastTransformation)
                        item.setIcon(scaled)
                except Exception:
                    pass
            
            # Add to appropriate list
            if is_ignored:
                self.ignored_list.addItem(item)
            else:
                self.active_list.addItem(item)
    
    def _filter_blocks(self):
        """Filter blocks based on search text."""
        search_text = self.search_input.text().lower()
        
        # Filter active list
        for i in range(self.active_list.count()):
            item = self.active_list.item(i)
            base_name = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(search_text not in base_name.lower())
        
        # Filter ignored list
        for i in range(self.ignored_list.count()):
            item = self.ignored_list.item(i)
            base_name = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(search_text not in base_name.lower())
    
    def _move_to_ignored(self):
        """Move selected blocks from active to ignored."""
        selected_items = self.active_list.selectedItems()
        for item in selected_items:
            base_name = item.data(Qt.ItemDataRole.UserRole)
            # Remove from active list
            row = self.active_list.row(item)
            self.active_list.takeItem(row)
            # Add to ignored list
            self.ignored_list.addItem(item)
        
        self._update_statistics()
    
    def _move_to_active(self):
        """Move selected blocks from ignored to active."""
        selected_items = self.ignored_list.selectedItems()
        for item in selected_items:
            base_name = item.data(Qt.ItemDataRole.UserRole)
            # Remove from ignored list
            row = self.ignored_list.row(item)
            self.ignored_list.takeItem(row)
            # Add to active list
            self.active_list.addItem(item)
        
        self._update_statistics()
    
    def _activate_all(self):
        """Move all blocks to active."""
        while self.ignored_list.count() > 0:
            item = self.ignored_list.takeItem(0)
            self.active_list.addItem(item)
        
        self._update_statistics()
    
    def _ignore_all(self):
        """Move all blocks to ignored."""
        while self.active_list.count() > 0:
            item = self.active_list.takeItem(0)
            self.ignored_list.addItem(item)
        
        self._update_statistics()
    
    def _reset_to_default(self):
        """Reset to default ignored blocks."""
        reply = QMessageBox.question(
            self,
            "Reset to Default",
            "This will reset all block settings to default (ignoring transparent blocks and default list). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset to default
            default_ignored = self.block_manager.default_ignored_blocks.copy()
            
            # Add transparent blocks
            from app.core.block_manager import BlockManager
            for block in self.block_manager.all_blocks:
                if block.has_transparency:
                    base_name = BlockManager.get_base_block_name(block.block_id)
                    default_ignored.add(base_name)
            
            # Update block manager
            self.block_manager.user_ignored_blocks = default_ignored
            
            # Repopulate lists
            self._populate_lists()
            self._update_statistics()
    
    def _save_and_apply(self):
        """Save settings and apply changes."""
        # Collect ignored blocks from ignored list
        new_ignored = set()
        
        for i in range(self.ignored_list.count()):
            item = self.ignored_list.item(i)
            base_name = item.data(Qt.ItemDataRole.UserRole)
            new_ignored.add(base_name)
        
        # Update block manager
        if self.block_manager:
            old_active_count = len(self.block_manager.active_blocks)
            
            self.block_manager.user_ignored_blocks = new_ignored
            self.block_manager._apply_filters()
            
            # Recreate matcher
            if self.block_manager.active_blocks:
                from app.minecraft.texturepack.matcher import BlockMatcher
                self.block_manager.matcher = BlockMatcher(
                    self.block_manager.active_blocks, 
                    allow_transparency=False
                )
            
            new_active_count = len(self.block_manager.active_blocks)
        
        self.settings_changed.emit()
        
        # Ask about re-rendering if blocks changed
        if old_active_count != new_active_count:
            reply = QMessageBox.question(
                self,
                "Re-render Image?",
                f"Block list has changed:\n"
                f"Previous active blocks: {old_active_count}\n"
                f"New active blocks: {new_active_count}\n\n"
                f"Do you want to re-render the current image with the new block list?\n"
                f"This will apply the changes to the canvas.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.re_render_requested.emit()
        
        self.accept()
