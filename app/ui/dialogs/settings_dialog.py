"""
Settings Dialog - PySide6 version
Manages block ignore list and application settings.
"""

from __future__ import annotations
from typing import Set

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QWidget, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap


class SettingsDialog(QDialog):
    """
    Dialog for managing application settings.

    The dialog only edits the two lists on screen; the BlockManager owns the
    filtering rules and is changed only on "Save & Apply".
    """
    
    settings_changed = Signal()
    re_render_requested = Signal()
    
    def __init__(self, block_manager, parent=None):
        super().__init__(parent)
        self.block_manager = block_manager
        self.setWindowTitle("Settings - Minepixel Editor")
        self.setModal(True)
        self.resize(900, 600)
        
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI layout."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("<h2>Settings</h2>")
        layout.addWidget(title)
        
        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
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

        self._populate_lists(self.block_manager.user_ignored_blocks)

    def _update_statistics(self):
        """Update statistics display from the lists on screen."""
        active = self.active_list.count()
        ignored = self.ignored_list.count()
        self.stats_label.setText(
            f"<b>Block Types:</b> {active + ignored} | "
            f"<b>Active:</b> {active} | "
            f"<b>Ignored:</b> {ignored}"
        )

    def _populate_lists(self, ignored_bases: Set[str]):
        """Populate both lists with base blocks, placing ignored_bases in the ignored list."""
        self.active_list.clear()
        self.ignored_list.clear()

        grouped = self.block_manager.get_grouped_blocks()

        for base_name in sorted(grouped):
            blocks = list(grouped[base_name]['blocks'].values())
            display_block = blocks[0]

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
            if base_name in ignored_bases:
                self.ignored_list.addItem(item)
            else:
                self.active_list.addItem(item)

        self._filter_blocks()
        self._update_statistics()

    def _ignored_bases_on_screen(self) -> Set[str]:
        """Base names currently in the ignored list."""
        return {
            self.ignored_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.ignored_list.count())
        }

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
            # Only the lists change here; the BlockManager is updated on Save
            self._populate_lists(self.block_manager.default_ignored_bases())

    def _save_and_apply(self):
        """Save settings and apply changes."""
        if self.active_list.count() == 0:
            QMessageBox.warning(
                self,
                "No Active Blocks",
                "At least one block must stay active to convert images."
            )
            return

        old_ignored = set(self.block_manager.user_ignored_blocks)
        old_active_count = len(self.block_manager.active_blocks)

        self.block_manager.set_ignored_blocks(self._ignored_bases_on_screen())
        new_active_count = len(self.block_manager.active_blocks)

        self.settings_changed.emit()

        # Ask about re-rendering if blocks changed
        if self.block_manager.user_ignored_blocks != old_ignored:
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
