"""
Main Application Module - PySide6 version
Manages the Qt application lifecycle and coordinates all components.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from PIL import Image

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QObject, Signal

from app.ui.main_window import MainWindow
from app.core.block_manager import BlockManager
from app.core.exporter import Exporter
from app.minecraft.image_mapper import ImageToBlockMapper
from app.minecraft.texturepack.matcher import BlockMatcher
from app.tools.brush_tool import BrushTool
from app.tools.picker_tool import PickerTool


class MinepixelEditorApp(QObject):
    """Main application class for Minepixel Editor (PySide6 version)."""
    
    # Signals for async operations
    loading_started = Signal()
    loading_progress = Signal(int, int)  # current, total
    loading_finished = Signal()
    
    def __init__(self):
        super().__init__()
        
        # Core components
        self.main_window: Optional[MainWindow] = None
        self.block_manager: Optional[BlockManager] = None
        self.matcher: Optional[BlockMatcher] = None
        self.exporter = Exporter()
        
        # Tools
        self.brush_tool = BrushTool()
        self.picker_tool = PickerTool()
        self.active_tool = None
        
        # Application state
        self.last_loaded_image: Optional[Path] = None
    
    def setup(self):
        """Initialize Qt application and setup UI."""
        # Create main window
        self.main_window = MainWindow()
        
        # Connect signals
        self._connect_signals()
        
        # Setup tools
        self._setup_tools()
        
        # Load blocks
        self._load_blocks()
        
        # Show window
        self.main_window.show()
        self.main_window.set_status("Ready")
    
    def _connect_signals(self):
        """Connects signals between components."""
        if not self.main_window:
            return
        
        # Main window signals
        self.main_window.load_image_requested.connect(self._on_load_image_requested)
        self.main_window.export_requested.connect(self._on_export_requested)
        self.main_window.export_block_list_requested.connect(self._on_export_block_list_requested)
        self.main_window.settings_requested.connect(self._on_settings_requested)
        self.main_window.brush_size_changed.connect(self._on_brush_size_changed)
        
        # Canvas signals
        canvas = self.main_window.get_canvas()
        canvas.block_changed.connect(self._on_block_changed)
        canvas.selection_changed.connect(self._on_selection_changed)
    
    def _setup_tools(self):
        """Setup tools and their connections."""
        # Set picker callback
        self.picker_tool.set_on_block_picked(self._on_block_picked_by_picker)
        
        # Connect tool buttons
        if self.main_window:
            self.main_window.brush_btn.clicked.connect(lambda: self._select_tool(self.brush_tool))
            self.main_window.picker_btn.clicked.connect(lambda: self._select_tool(self.picker_tool))
        
        # Select brush tool by default
        self._select_tool(self.brush_tool)
    
    def _select_tool(self, tool):
        """Selects a tool and updates UI."""
        self.active_tool = tool
        if self.main_window:
            self.main_window.get_canvas().set_active_tool(tool)
            
            # Update button states
            if tool == self.brush_tool:
                self.main_window.brush_btn.setChecked(True)
                self.main_window.picker_btn.setChecked(False)
            elif tool == self.picker_tool:
                self.main_window.brush_btn.setChecked(False)
                self.main_window.picker_btn.setChecked(True)
            
            self.main_window.set_status(f"Tool selected: {tool.name}")
    
    def _load_blocks(self):
        """Load and initialize blocks."""
        if not self.main_window:
            return
        
        self.main_window.set_status("Loading textures...")
        
        texture_path = Path("assets/minecraft_textures/blocks")
        self.block_manager = BlockManager(texture_path)
        self.block_manager.load_blocks()
        
        # Initialize matcher
        self.matcher = BlockMatcher(self.block_manager.active_blocks)
        
        # Populate block palette
        self.main_window.set_blocks(self.block_manager.active_blocks)
        
        # Set first block as default if available
        if self.block_manager.active_blocks:
            first_block = self.block_manager.active_blocks[0]
            self.main_window.get_canvas().set_current_block(first_block)
        
        # Update status
        active_count = len(self.block_manager.active_blocks)
        total_count = len(self.block_manager.all_blocks)
        ignored_count = total_count - active_count
        
        self.main_window.set_status(
            f"Loaded {total_count} textures ({active_count} active, {ignored_count} ignored)"
        )
        
        # Create test grid
        self._create_test_grid()
    
    def _create_test_grid(self):
        """Creates a test grid with active blocks."""
        if not self.block_manager or not self.block_manager.active_blocks:
            if self.main_window:
                self.main_window.set_status("ERROR: No active blocks available")
            return
        
        # Get solid blocks
        solid_blocks = [b for b in self.block_manager.active_blocks if not b.has_transparency]
        if len(solid_blocks) < 10:
            solid_blocks = self.block_manager.active_blocks
        
        # Create pattern grid
        grid_width = 64
        grid_height = 64
        
        grid = []
        for y in range(grid_height):
            row = []
            for x in range(grid_width):
                block_index = (x + y) % len(solid_blocks)
                row.append(solid_blocks[block_index])
            grid.append(row)
        
        if self.main_window:
            self.main_window.set_grid(grid)
            canvas = self.main_window.get_canvas()
            canvas.zoom_to_fit()
            
            # Set current block for painting
            if solid_blocks:
                canvas.set_current_block(solid_blocks[0])
            
            self.main_window.set_status(f"Test grid created: {grid_width}x{grid_height}")
    
    def _on_load_image_requested(self, file_path: str):
        """Handles load image request."""
        path = Path(file_path)
        if not path.exists():
            if self.main_window:
                self.main_window.show_error("Error", f"File not found: {path}")
            return
        
        try:
            with Image.open(path) as img:
                width, height = img.size
            
            # Check if resize is needed (max 256x256)
            max_dimension = 256
            needs_resize = width > max_dimension or height > max_dimension
            
            if needs_resize:
                # Calculate proportional resize
                scale = max_dimension / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Ask user for confirmation
                if self.main_window:
                    message = (
                        f"The selected image exceeds the maximum size of 256x256 pixels.\n\n"
                        f"Original size: {width}x{height} pixels\n"
                        f"Will be resized to: {new_width}x{new_height} pixels\n\n"
                        f"This ensures the final pixel art fits within Minecraft's "
                        f"performance limits (256x256 blocks maximum).\n\n"
                        f"Continue?"
                    )
                    
                    if not self.main_window.ask_question("Image Resize Required", message):
                        self.main_window.set_status("Image import cancelled")
                        return
                
                target_size = (new_width, new_height)
            else:
                target_size = None
            
            self.last_loaded_image = path
            self._convert_and_load_image(path, target_size)
            
        except Exception as e:
            if self.main_window:
                self.main_window.show_error("Error", f"Error loading image: {e}")
    
    def _convert_and_load_image(self, file_path: Path, target_size=None):
        """Converts and loads image to canvas."""
        if not self.main_window or not self.matcher:
            return
        
        try:
            self.main_window.set_status(f"Loading image: {file_path.name}...")
            self.main_window.show_progress(0, 100)
            
            # Load image
            with Image.open(file_path) as img:
                # Resize if needed
                if target_size:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                width, height = img.size
                
                # Create mapper
                mapper = ImageToBlockMapper(self.matcher)
                
                self.main_window.set_status(f"Converting {width}x{height} image to blocks...")
                
                # Progress callback
                def progress_callback(progress):
                    self.main_window.show_progress(int(progress * 100), 100, f"Rendering {file_path.name}...")
                
                # Convert to block grid
                grid = mapper.map_image_to_blocks(img, progress_callback=progress_callback)
                
                self.main_window.set_status("Finalizing...")
                self.main_window.show_progress(100, 100, f"Finalizing {file_path.name}...")
                
                # Set grid on canvas
                self.main_window.set_grid(grid)
                self.main_window.get_canvas().zoom_to_fit()
                
                # Update statistics
                self._update_block_statistics(grid)
                
                self.main_window.hide_progress()
                self.main_window.set_status(
                    f"Loaded {file_path.name} ({width}x{height})"
                )
            
        except Exception as e:
            self.main_window.show_error("Error", f"Error converting image: {e}")
            self.main_window.set_status("Error converting image")
    
    def _on_export_requested(self):
        """Handles export request."""
        if not self.main_window:
            return
        
        canvas = self.main_window.get_canvas()
        if not canvas._grid:
            self.main_window.show_warning("Warning", "No image to export. Load an image first.")
            return
        
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Image",
            "",
            "PNG Images (*.png)"
        )
        
        if file_path:
            try:
                path = Path(file_path)
                if path.suffix.lower() != '.png':
                    path = path.with_suffix('.png')
                
                self.main_window.set_status(f"Exporting image to {path.name}...")
                self.exporter.export_image(canvas._grid, path)
                self.main_window.set_status(f"Exported image to {path.name}")
                self.main_window.show_info("Success", f"Image exported to {path.name}")
            except Exception as e:
                self.main_window.show_error("Error", f"Export error: {e}")
    
    def _on_export_block_list_requested(self, file_path: Path):
        """Handles export block list request."""
        if not self.main_window:
            return
        
        canvas = self.main_window.get_canvas()
        if not canvas or not canvas._grid:
            self.main_window.show_error("Export Error", "No grid to export. Load an image first.")
            return
        
        try:
            from app.core.block_manager import BlockManager
            
            # Analyze grid with variants
            block_stats = self.exporter.analyze_grid_blocks(
                canvas._grid,
                BlockManager.get_base_block_name,
                BlockManager.get_block_variant
            )
            
            # Export to file
            self.exporter.export_block_list(block_stats, file_path)
            self.main_window.set_status(f"Block list exported to {file_path.name}")
            self.main_window.show_info("Export Success", f"Block list exported to:\\n{file_path}")
        except Exception as e:
            self.main_window.show_error("Export Error", f"Failed to export block list: {e}")
    
    def _on_settings_requested(self):
        """Handles settings request."""
        if self.main_window and self.block_manager:
            from app.ui.dialogs.settings_dialog import SettingsDialog
            
            dialog = SettingsDialog(self.block_manager, self.main_window)
            dialog.settings_changed.connect(self._on_settings_changed)
            dialog.re_render_requested.connect(self._on_re_render_requested)
            dialog.exec()
    
    def _on_settings_changed(self):
        """Handles settings change - update palette with new active blocks."""
        if self.main_window and self.block_manager:
            self.main_window.set_blocks(self.block_manager.active_blocks)
            self.main_window.set_status(
                f"Settings updated - {len(self.block_manager.active_blocks)} active blocks"
            )
    
    def _on_re_render_requested(self):
        """Handles re-render request after settings change."""
        if not self.main_window:
            return
        
        canvas = self.main_window.get_canvas()
        if not canvas or not canvas._grid:
            return
        
        try:
            # Get current grid dimensions
            height = len(canvas._grid)
            width = len(canvas._grid[0]) if height > 0 else 0
            
            if width == 0 or height == 0:
                return
            
            # Convert grid back to image, then re-convert with new blocks
            # Create a temporary image from current colors
            from PIL import Image
            import numpy as np
            
            # Extract colors from current grid
            img_array = np.zeros((height, width, 3), dtype=np.uint8)
            for y in range(height):
                for x in range(width):
                    block = canvas._grid[y][x]
                    if block and block.avg_color:
                        img_array[y, x] = block.avg_color[:3]
            
            img = Image.fromarray(img_array, 'RGB')
            
            # Show progress
            self.main_window.show_progress(0, 100, "Re-rendering with new blocks...")
            
            # Re-map with new blocks
            from app.minecraft.image_mapper import ImageToBlockMapper
            mapper = ImageToBlockMapper(self.block_manager.matcher)
            
            def progress_callback(progress: float):
                progress_percent = int(progress * 100)
                self.main_window.show_progress(progress_percent, 100, "Re-rendering...")
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
            
            new_grid = mapper.map_image_to_blocks(img, progress_callback=progress_callback)
            
            # Update canvas
            self.main_window.show_progress(100, 100, "Finalizing...")
            self.main_window.set_grid(new_grid)
            
            # Update statistics
            self._update_block_statistics(new_grid)
            
            self.main_window.hide_progress()
            self.main_window.set_status("Image re-rendered with new block list")
            
        except Exception as e:
            self.main_window.hide_progress()
            self.main_window.show_error("Re-render Error", f"Failed to re-render image: {e}")
            self.main_window.set_status("Re-render failed")
    
    def _on_brush_size_changed(self, size: int):
        """Handles brush size change."""
        if self.brush_tool:
            self.brush_tool.set_brush_size(size)
            self.main_window.set_status(f"Brush size: {size}x{size}")
    
    def _on_block_changed(self, x: int, y: int, block):
        """Called when a block is changed (painted)."""
        if not self.main_window:
            return
        
        canvas = self.main_window.get_canvas()
        info = canvas.get_canvas_info()
        
        self.main_window.set_status(
            f"Block changed at ({x}, {y}) -> {block.block_id} | "
            f"Zoom: {info['zoom_level']:.1f}x | Grid: {info['grid_width']}x{info['grid_height']}"
        )
    
    def _on_selection_changed(self, x: int, y: int):
        """Called when hover position changes."""
        if not self.main_window:
            return
        
        canvas = self.main_window.get_canvas()
        
        if 0 <= x < canvas._grid_width and 0 <= y < canvas._grid_height:
            block = canvas.get_block_at(x, y)
            if block:
                info = canvas.get_canvas_info()
                self.main_window.set_status(
                    f"Position: ({x}, {y}) -> {block.block_id} | "
                    f"Zoom: {info['zoom_level']:.1f}x | "
                    f"Left: Paint | Middle: Pan | Scroll: Zoom"
                )
    
    def _on_block_picked_by_picker(self, block):
        """Handles block picked by eyedropper tool."""
        if self.main_window:
            # Update palette selection
            self.main_window.block_palette.set_selected_block(block)
            self.main_window._selected_block = block
            self.main_window.canvas.set_current_block(block)
            self.main_window._update_selected_block_display()
            self.main_window.set_status(f"Block picked: {block.block_id}")
    
    def _update_block_statistics(self, grid: List[List]):
        """Updates block statistics display."""
        if not self.main_window or not grid:
            return
        
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QPushButton, QWidget, QFrame, QLabel
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        from app.core.block_manager import BlockManager
        
        # Clear previous widgets
        while self.main_window.stats_layout.count():
            item = self.main_window.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Analyze grid with variants
        block_stats = self.exporter.analyze_grid_blocks(
            grid,
            BlockManager.get_base_block_name,
            BlockManager.get_block_variant
        )
        
        if not block_stats:
            self.main_window.totals_label.setText("No blocks in grid")
            return
        
        # Calculate totals
        total_blocks = sum(stats['total'] for stats in block_stats.values())
        unique_types = len(block_stats)
        
        # Update totals
        self.main_window.totals_label.setText(
            f"<b>Total Blocks:</b> {total_blocks:,}<br>"
            f"<b>Unique Types:</b> {unique_types}"
        )
        
        # Sort by count
        sorted_blocks = sorted(block_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        # Add all blocks with images and dropdowns
        for base_name, stats in sorted_blocks:
            display_block = stats['blocks'].get('normal') or next(iter(stats['blocks'].values()))
            has_variants = len(stats['variants']) > 1
            
            # Create block entry
            block_frame = QFrame()
            block_frame.setFrameShape(QFrame.Shape.StyledPanel)
            block_layout = QVBoxLayout(block_frame)
            block_layout.setContentsMargins(5, 5, 5, 5)
            block_layout.setSpacing(3)
            
            # Header with image and name
            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(8)
            
            # Add texture image
            if display_block and display_block.texture_path.exists():
                try:
                    texture_label = QLabel()
                    pixmap = QPixmap(str(display_block.texture_path))
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
                        texture_label.setPixmap(scaled_pixmap)
                        header_layout.addWidget(texture_label)
                except Exception:
                    pass
            
            # Add name and count
            # Remove 'minecraft:' prefix for cleaner display
            display_name = base_name.replace('minecraft:', '')
            name_label = QLabel(f"<b>{display_name}:</b> {stats['total']} blocks")
            header_layout.addWidget(name_label, stretch=1)
            block_layout.addWidget(header_widget)
            
            # Add variants dropdown if multiple
            if has_variants:
                # Create collapsible section
                variants_btn = QPushButton(f"▶ {len(stats['variants'])} variants")
                variants_btn.setFlat(True)
                variants_btn.setStyleSheet("text-align: left; padding: 2px;")
                
                # Variants container
                variants_widget = QWidget()
                variants_layout = QVBoxLayout(variants_widget)
                variants_layout.setContentsMargins(20, 0, 0, 0)
                variants_layout.setSpacing(2)
                variants_widget.setVisible(False)
                
                # Add each variant
                for variant, count in sorted(stats['variants'].items(), key=lambda x: x[1], reverse=True):
                    variant_block = stats['blocks'].get(variant)
                    variant_widget = QWidget()
                    variant_layout = QHBoxLayout(variant_widget)
                    variant_layout.setContentsMargins(0, 0, 0, 0)
                    variant_layout.setSpacing(8)
                    
                    # Variant texture
                    if variant_block and variant_block.texture_path.exists():
                        try:
                            var_texture_label = QLabel()
                            var_pixmap = QPixmap(str(variant_block.texture_path))
                            if not var_pixmap.isNull():
                                var_scaled = var_pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
                                var_texture_label.setPixmap(var_scaled)
                                variant_layout.addWidget(var_texture_label)
                        except Exception:
                            pass
                    
                    var_label = QLabel(f"{variant.capitalize()}: {count}")
                    variant_layout.addWidget(var_label, stretch=1)
                    variants_layout.addWidget(variant_widget)
                
                # Toggle function
                def make_toggle(btn, widget):
                    def toggle():
                        visible = not widget.isVisible()
                        widget.setVisible(visible)
                        btn.setText(("▼" if visible else "▶") + btn.text()[1:])
                    return toggle
                
                variants_btn.clicked.connect(make_toggle(variants_btn, variants_widget))
                block_layout.addWidget(variants_btn)
                block_layout.addWidget(variants_widget)
            
            self.main_window.stats_layout.addWidget(block_frame)
        
        # Add stretch at the end
        self.main_window.stats_layout.addStretch()

    
    def run(self):
        """Run the application main loop."""
        if not self.main_window:
            return 1
        
        return QApplication.instance().exec()
