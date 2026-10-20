"""
Main Application Module - PySide6 version
Manages the Qt application lifecycle and coordinates all components.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from PIL import Image

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QObject, QTimer, Signal

from app.ui.main_window import MainWindow
from app.ui.dialogs.resize_dialog import ResizeDialog
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
        self.last_target_size: Optional[tuple[int, int]] = None

        # Block statistics refresh after painting: each painted block restarts the
        # timer, so the panel is rebuilt once, shortly after the stroke stops
        self._stats_refresh_timer = QTimer(self)
        self._stats_refresh_timer.setSingleShot(True)
        self._stats_refresh_timer.setInterval(200)
        self._stats_refresh_timer.timeout.connect(self._refresh_block_statistics)
        self._thumbnail_cache: dict = {}
        self._expanded_variant_sections: set = set()

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
            
            # Show resize dialog
            if self.main_window:
                dialog = ResizeDialog(width, height, self.main_window)
                if dialog.exec() == ResizeDialog.DialogCode.Accepted:
                    target_width, target_height = dialog.get_dimensions()
                    target_size = (target_width, target_height)
                    
                    self.last_loaded_image = path
                    self.last_target_size = target_size
                    self._convert_and_load_image(path, target_size)
                else:
                    self.main_window.set_status("Image import cancelled")
            
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
            # Keep the app matcher in sync with the filtered block list
            self.matcher = self.block_manager.matcher
            self.main_window.set_blocks(self.block_manager.active_blocks)
            self.main_window.set_status(
                f"Settings updated - {len(self.block_manager.active_blocks)} active blocks"
            )
    
    def _on_re_render_requested(self):
        """Handles re-render request after settings change."""
        if not self.main_window:
            return
        
        # Re-convert from the original image (not from the current blocks' average
        # colors), so repeated re-renders don't lose fidelity
        if not self.last_loaded_image:
            self.main_window.set_status("No imported image to re-render")
            return

        if not self.last_loaded_image.exists():
            self.main_window.show_error(
                "Re-render Error",
                f"Original image not found: {self.last_loaded_image}"
            )
            return

        self._convert_and_load_image(self.last_loaded_image, self.last_target_size)
    
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

        # Material list: refresh once painting pauses (rebuilding it per block is too slow)
        self._stats_refresh_timer.start()

    def _refresh_block_statistics(self):
        """Rebuilds the material list from the blocks currently on the canvas."""
        if self.main_window:
            self._update_block_statistics(self.main_window.get_canvas()._grid)

    def _thumbnail(self, block, size: int):
        """Returns a cached, scaled texture thumbnail (None if it can't be loaded)."""
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt

        key = (str(block.texture_path), size)
        if key not in self._thumbnail_cache:
            pixmap = QPixmap(str(block.texture_path))
            self._thumbnail_cache[key] = None if pixmap.isNull() else pixmap.scaled(
                size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
            )
        return self._thumbnail_cache[key]

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
        from app.core.block_manager import BlockManager

        # The list is rebuilt after every stroke: keep the scroll position
        scroll_bar = self.main_window.stats_scroll_area.verticalScrollBar()
        scroll_value = scroll_bar.value()

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
            thumbnail = self._thumbnail(display_block, 24) if display_block else None
            if thumbnail:
                texture_label = QLabel()
                texture_label.setPixmap(thumbnail)
                header_layout.addWidget(texture_label)
            
            # Add name and count
            # Remove 'minecraft:' prefix for cleaner display
            display_name = base_name.replace('minecraft:', '')
            name_label = QLabel(f"<b>{display_name}:</b> {stats['total']} blocks")
            header_layout.addWidget(name_label, stretch=1)
            block_layout.addWidget(header_widget)
            
            # Add variants dropdown if multiple
            if has_variants:
                # Create collapsible section
                # (sections the user expanded stay expanded across refreshes)
                expanded = base_name in self._expanded_variant_sections
                variants_btn = QPushButton(f"{'▼' if expanded else '▶'} {len(stats['variants'])} variants")
                variants_btn.setFlat(True)
                variants_btn.setStyleSheet("text-align: left; padding: 2px;")

                # Variants container
                variants_widget = QWidget()
                variants_layout = QVBoxLayout(variants_widget)
                variants_layout.setContentsMargins(20, 0, 0, 0)
                variants_layout.setSpacing(2)
                variants_widget.setVisible(expanded)
                
                # Add each variant
                for variant, count in sorted(stats['variants'].items(), key=lambda x: x[1], reverse=True):
                    variant_block = stats['blocks'].get(variant)
                    variant_widget = QWidget()
                    variant_layout = QHBoxLayout(variant_widget)
                    variant_layout.setContentsMargins(0, 0, 0, 0)
                    variant_layout.setSpacing(8)
                    
                    # Variant texture
                    var_thumbnail = self._thumbnail(variant_block, 20) if variant_block else None
                    if var_thumbnail:
                        var_texture_label = QLabel()
                        var_texture_label.setPixmap(var_thumbnail)
                        variant_layout.addWidget(var_texture_label)
                    
                    var_label = QLabel(f"{variant.capitalize()}: {count}")
                    variant_layout.addWidget(var_label, stretch=1)
                    variants_layout.addWidget(variant_widget)
                
                # Toggle function
                def make_toggle(btn, widget, name):
                    def toggle():
                        visible = not widget.isVisible()
                        widget.setVisible(visible)
                        btn.setText(("▼" if visible else "▶") + btn.text()[1:])
                        if visible:
                            self._expanded_variant_sections.add(name)
                        else:
                            self._expanded_variant_sections.discard(name)
                    return toggle

                variants_btn.clicked.connect(make_toggle(variants_btn, variants_widget, base_name))
                block_layout.addWidget(variants_btn)
                block_layout.addWidget(variants_widget)
            
            self.main_window.stats_layout.addWidget(block_frame)
        
        # Add stretch at the end
        self.main_window.stats_layout.addStretch()

        # Restore the scroll position once the new widgets are laid out
        QTimer.singleShot(0, lambda: scroll_bar.setValue(scroll_value))

    
    def run(self):
        """Run the application main loop."""
        if not self.main_window:
            return 1
        
        return QApplication.instance().exec()
