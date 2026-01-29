"""
Main Window - PySide6 version of the Minepixel Editor.
"""

from __future__ import annotations
from typing import Optional, List
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QToolBar, QStatusBar, QPushButton, QLabel, QDockWidget,
    QFileDialog, QMessageBox, QProgressBar, QScrollArea, QSlider, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap

from app.ui.canvas_widget import CanvasWidget
from app.ui.block_palette import BlockPalette
from app.minecraft.texturepack.models import BlockTexture


class MainWindow(QMainWindow):
    """Main window for Minepixel Editor (PySide6 version)."""
    
    # Signals
    load_image_requested = Signal(str)
    export_requested = Signal()
    export_block_list_requested = Signal(Path)
    settings_requested = Signal()
    brush_size_changed = Signal(int)
    
    def __init__(self):
        super().__init__()
        
        # State
        self._current_blocks: List[BlockTexture] = []
        self._selected_block: Optional[BlockTexture] = None
        
        # Setup UI
        self.setWindowTitle("Minepixel Editor - Minecraft Pixel Art Generator")
        self.setGeometry(100, 100, 1600, 900)
        
        # Create widgets
        self._create_widgets()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_dock_widgets()
        self._create_status_bar()
        
        # Connect signals
        self._connect_signals()
    
    def _create_widgets(self):
        """Creates main widgets."""
        # Central widget - Canvas
        self.canvas = CanvasWidget()
        self.setCentralWidget(self.canvas)
    
    def _create_menu_bar(self):
        """Creates menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        load_action = QAction("&Load Image...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._on_load_image)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("&Export Image...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export_image)
        file_menu.addAction(export_action)
        
        export_list_action = QAction("Export Block &List...", self)
        export_list_action.setShortcut("Ctrl+L")
        export_list_action.triggered.connect(self._on_export_block_list)
        file_menu.addAction(export_list_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self._on_settings)
        edit_menu.addAction(settings_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        zoom_fit_action = QAction("&Fit to Window", self)
        zoom_fit_action.setShortcut("Ctrl+0")
        zoom_fit_action.triggered.connect(self.canvas.zoom_to_fit)
        view_menu.addAction(zoom_fit_action)
        
        zoom_reset_action = QAction("&Reset View", self)
        zoom_reset_action.setShortcut("Ctrl+R")
        zoom_reset_action.triggered.connect(self.canvas.reset_view)
        view_menu.addAction(zoom_reset_action)
        
        view_menu.addSeparator()
        
        grid_action = QAction("Toggle &Grid", self)
        grid_action.setShortcut("Ctrl+G")
        grid_action.setCheckable(True)
        grid_action.setChecked(True)
        grid_action.triggered.connect(self._on_toggle_grid)
        view_menu.addAction(grid_action)
        self.grid_action = grid_action
    
    def _create_toolbar(self):
        """Creates main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Load Image
        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self._on_load_image)
        toolbar.addWidget(load_btn)
        
        # Export
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export_image)
        toolbar.addWidget(export_btn)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_btn = QPushButton("Zoom +")
        zoom_in_btn.clicked.connect(self.canvas.zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("Zoom -")
        zoom_out_btn.clicked.connect(self.canvas.zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        zoom_fit_btn = QPushButton("Fit")
        zoom_fit_btn.clicked.connect(self.canvas.zoom_to_fit)
        toolbar.addWidget(zoom_fit_btn)
        
        zoom_reset_btn = QPushButton("Reset")
        zoom_reset_btn.clicked.connect(self.canvas.reset_view)
        toolbar.addWidget(zoom_reset_btn)
        
        toolbar.addSeparator()
        
        # Grid toggle
        grid_btn = QPushButton("Toggle Grid")
        grid_btn.setCheckable(True)
        grid_btn.setChecked(True)
        grid_btn.clicked.connect(self._on_toggle_grid)
        toolbar.addWidget(grid_btn)
        self.grid_btn = grid_btn
        
        toolbar.addSeparator()
        
        # Settings
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)
    
    def _create_dock_widgets(self):
        """Creates dock widgets."""
        # Left dock - Tools & Palette
        left_dock = QDockWidget("Tools & Palette", self)
        left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Tool selection
        tools_label = QLabel("<b>Tools</b>")
        left_layout.addWidget(tools_label)
        
        tools_layout = QHBoxLayout()
        
        self.brush_btn = QPushButton("🖌️ Brush")
        self.brush_btn.setCheckable(True)
        self.brush_btn.setChecked(True)
        tools_layout.addWidget(self.brush_btn)
        
        self.picker_btn = QPushButton("💧 Picker")
        self.picker_btn.setCheckable(True)
        tools_layout.addWidget(self.picker_btn)
        
        left_layout.addLayout(tools_layout)
        
        # Brush size controls
        brush_size_group = QGroupBox("Brush Size")
        brush_size_layout = QVBoxLayout(brush_size_group)
        
        # Slider
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Size:"))
        
        from PySide6.QtWidgets import QSlider
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(15)
        self.brush_size_slider.setValue(1)
        self.brush_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brush_size_slider.setTickInterval(2)
        self.brush_size_slider.setMaximumWidth(120)  # Limit slider width
        self.brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        slider_layout.addWidget(self.brush_size_slider)
        
        self.brush_size_label = QLabel("1x1")
        self.brush_size_label.setMinimumWidth(35)
        slider_layout.addWidget(self.brush_size_label)
        
        brush_size_layout.addLayout(slider_layout)
        
        # Quick size buttons (reduced to 1x1, 3x3, 5x5, 7x7)
        quick_label = QLabel("Quick:")
        brush_size_layout.addWidget(quick_label)
        
        quick_buttons_layout = QHBoxLayout()
        for size in [1, 3, 5, 7]:
            btn = QPushButton(f"{size}x{size}")
            btn.setMaximumWidth(45)
            btn.clicked.connect(lambda checked, s=size: self._set_brush_size(s))
            quick_buttons_layout.addWidget(btn)
        
        brush_size_layout.addLayout(quick_buttons_layout)
        left_layout.addWidget(brush_size_group)
        
        # Selected block display
        selected_label = QLabel("<b>Selected Block</b>")
        left_layout.addWidget(selected_label)
        
        # Selected block container (texture + info)
        selected_container = QWidget()
        selected_layout = QHBoxLayout(selected_container)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        selected_layout.setSpacing(8)
        
        # Texture thumbnail
        self.selected_texture_label = QLabel()
        self.selected_texture_label.setFixedSize(48, 48)
        self.selected_texture_label.setStyleSheet("border: 1px solid #ccc;")
        selected_layout.addWidget(self.selected_texture_label)
        
        # Block info
        self.selected_block_label = QLabel("No block selected")
        self.selected_block_label.setWordWrap(True)
        selected_layout.addWidget(self.selected_block_label, stretch=1)
        
        left_layout.addWidget(selected_container)
        
        # Block palette
        palette_label = QLabel("<b>Block Palette</b>")
        left_layout.addWidget(palette_label)
        
        self.block_palette = BlockPalette()
        left_layout.addWidget(self.block_palette)
        
        left_widget.setLayout(left_layout)
        left_dock.setWidget(left_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)
        
        # Right dock - Statistics
        right_dock = QDockWidget("Block Statistics", self)
        right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        stats_label = QLabel("<b>Statistics</b>")
        right_layout.addWidget(stats_label)
        
        # Totals section (fixed, not scrollable)
        self.totals_label = QLabel("Load an image to see statistics")
        self.totals_label.setWordWrap(True)
        right_layout.addWidget(self.totals_label)
        
        # Scrollable blocks list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        self.stats_layout = QVBoxLayout(scroll_widget)
        self.stats_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_widget.setLayout(self.stats_layout)
        scroll_area.setWidget(scroll_widget)
        right_layout.addWidget(scroll_area)
        
        # Export button
        export_list_btn = QPushButton("Export Block List to TXT")
        export_list_btn.clicked.connect(self._on_export_block_list)
        right_layout.addWidget(export_list_btn)
        
        right_widget.setLayout(right_layout)
        right_dock.setWidget(right_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)
        
        # Set default width for right dock (statistics)
        right_dock.setMinimumWidth(350)
        self.resizeDocks([right_dock], [400], Qt.Orientation.Horizontal)
    
    def _create_status_bar(self):
        """Creates status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Progress area (text + bar)
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        self.status_bar.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def _connect_signals(self):
        """Connects signals."""
        self.block_palette.block_selected.connect(self._on_palette_block_selected)
        self.canvas.block_changed.connect(self._on_canvas_block_changed)
        self.canvas.selection_changed.connect(self._on_canvas_selection_changed)
    
    # Event handlers
    def _on_load_image(self):
        """Handles load image button."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_path:
            self.load_image_requested.emit(file_path)
    
    def _on_export_image(self):
        """Handles export image button."""
        self.export_requested.emit()
    
    def _on_export_block_list(self):
        """Handles export block list button."""
        # Check if we have a canvas with grid
        if not self.canvas or not self.canvas._grid:
            self.show_warning("Export Error", "No grid loaded. Load an image first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Block List",
            "",
            "Text Files (*.txt)"
        )
        
        if file_path:
            # Request export from application
            from pathlib import Path
            self.export_block_list_requested.emit(Path(file_path))
    
    def _on_settings(self):
        """Handles settings button."""
        self.settings_requested.emit()
    
    def _on_toggle_grid(self):
        """Toggles grid visibility."""
        show_grid = self.grid_action.isChecked()
        self.canvas.set_show_grid(show_grid)
        self.grid_btn.setChecked(show_grid)
    
    def _on_palette_block_selected(self, block: BlockTexture):
        """Handles block selection from palette."""
        self._selected_block = block
        self.canvas.set_current_block(block)
        self._update_selected_block_display()
    
    def _on_canvas_block_changed(self, x: int, y: int, block: BlockTexture):
        """Handles block change on canvas."""
        # Update statistics
        pass
    
    def _on_canvas_selection_changed(self, x: int, y: int):
        """Handles cursor position change on canvas."""
        block = self.canvas.get_block_at(x, y)
        if block:
            self.status_label.setText(f"Position: ({x}, {y}) | Block: {block.block_id}")
        else:
            self.status_label.setText(f"Position: ({x}, {y})")
    
    # Public methods
    def set_blocks(self, blocks: List[BlockTexture]):
        """Sets available blocks."""
        self._current_blocks = blocks
        self.block_palette.set_blocks(blocks)
        
        # Auto-select first block if nothing is selected
        if blocks and not self._selected_block:
            first_block = blocks[0]
            self._selected_block = first_block
            self.block_palette.set_selected_block(first_block)
            self.canvas.set_current_block(first_block)
            self._update_selected_block_display()
    
    def set_grid(self, grid: List[List[BlockTexture]]):
        """Sets the block grid."""
        # Preserve current block selection
        current_block = self.canvas.get_current_block()
        
        self.canvas.set_grid(grid)
        
        # Restore current block after grid change
        if current_block:
            self.canvas.set_current_block(current_block)
    
    def get_canvas(self) -> CanvasWidget:
        """Returns canvas widget."""
        return self.canvas
    
    def set_status(self, message: str):
        """Sets status bar message."""
        self.status_label.setText(message)
    
    def show_progress(self, value: int, maximum: int, text: str = ""):
        """Shows progress bar with value and optional text."""
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(int(value))
        if text:
            self.progress_label.setText(text)
    
    def hide_progress(self):
        """Hides progress bar."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.progress_label.setText("")
        self.progress_bar.setVisible(False)
    
    def _update_selected_block_display(self):
        """Updates selected block display."""
        if self._selected_block:
            # Remove 'minecraft:' prefix for display
            display_name = self._selected_block.block_id.replace('minecraft:', '')
            
            # Update text
            self.selected_block_label.setText(
                f"<b>{display_name}</b><br>"
                f"Transparent: {'Yes' if self._selected_block.has_transparency else 'No'}"
            )
            
            # Update texture thumbnail
            if self._selected_block.texture_path.exists():
                try:
                    from PySide6.QtGui import QPixmap
                    pixmap = QPixmap(str(self._selected_block.texture_path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            48, 48,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.FastTransformation
                        )
                        self.selected_texture_label.setPixmap(scaled)
                except Exception:
                    self.selected_texture_label.clear()
            else:
                self.selected_texture_label.clear()
        else:
            self.selected_block_label.setText("No block selected")
            self.selected_texture_label.clear()
    
    def show_error(self, title: str, message: str):
        """Shows error dialog."""
        QMessageBox.critical(self, title, message)
    
    def show_info(self, title: str, message: str):
        """Shows info dialog."""
        QMessageBox.information(self, title, message)
    
    def show_warning(self, title: str, message: str):
        """Shows warning dialog."""
        QMessageBox.warning(self, title, message)
    
    def ask_question(self, title: str, message: str) -> bool:
        """Shows yes/no question dialog."""
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def _on_toggle_grid(self, checked: bool):
        """Toggles grid visibility."""
        self.canvas.set_show_grid(checked)
        self.canvas.update()
    
    def _on_brush_size_changed(self, value: int):
        """Handles brush size slider change."""
        # Ensure odd number for symmetry
        if value % 2 == 0:
            value += 1
            self.brush_size_slider.setValue(value)
        
        self.brush_size_label.setText(f"{value}x{value}")
        self.brush_size_changed.emit(value)
    
    def _set_brush_size(self, size: int):
        """Sets brush size from button."""
        self.brush_size_slider.setValue(size)
