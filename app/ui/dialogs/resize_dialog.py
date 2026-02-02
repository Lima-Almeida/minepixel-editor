"""
Resize Dialog Module
Provides a dialog for configuring image resize options when importing.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSpinBox, QRadioButton, QGroupBox,
    QButtonGroup
)
from PySide6.QtCore import Qt


class ResizeDialog(QDialog):
    """Dialog for selecting image resize dimensions."""
    
    def __init__(self, original_width: int, original_height: int, parent=None):
        super().__init__(parent)
        
        self.original_width = original_width
        self.original_height = original_height
        self.aspect_ratio = original_width / original_height
        
        # Calculate initial dimensions (limit to 256 on the larger side)
        max_dimension = 256
        if max(original_width, original_height) > max_dimension:
            scale = max_dimension / max(original_width, original_height)
            self.target_width = max(1, round(original_width * scale))
            self.target_height = max(1, round(original_height * scale))
        else:
            self.target_width = original_width
            self.target_height = original_height
        
        self._setup_ui()
        self._update_dimensions()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Set Pixel Art Dimensions")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Original size info
        info_layout = QVBoxLayout()
        info_label = QLabel("<b>Original Image Size:</b>")
        size_label = QLabel(f"{self.original_width} x {self.original_height} pixels")
        info_layout.addWidget(info_label)
        info_layout.addWidget(size_label)
        layout.addLayout(info_layout)
        
        layout.addSpacing(20)
        
        # Dimension selection group
        dim_group = QGroupBox("Choose Which Dimension to Set")
        dim_layout = QVBoxLayout()
        
        # Radio buttons for width/height selection
        self.width_radio = QRadioButton("Set Width (height adjusts automatically)")
        self.height_radio = QRadioButton("Set Height (width adjusts automatically)")
        self.width_radio.setChecked(True)
        
        # Button group to ensure only one is selected
        self.dimension_group = QButtonGroup(self)
        self.dimension_group.addButton(self.width_radio)
        self.dimension_group.addButton(self.height_radio)
        
        dim_layout.addWidget(self.width_radio)
        dim_layout.addWidget(self.height_radio)
        dim_group.setLayout(dim_layout)
        layout.addWidget(dim_group)
        
        layout.addSpacing(10)
        
        # Width input
        width_layout = QHBoxLayout()
        width_label = QLabel("Width (blocks):")
        width_label.setMinimumWidth(120)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 512)
        self.width_spin.setValue(self.target_width)
        self.width_spin.setSuffix(" blocks")
        width_layout.addWidget(width_label)
        width_layout.addWidget(self.width_spin)
        width_layout.addStretch()
        layout.addLayout(width_layout)
        
        # Height input
        height_layout = QHBoxLayout()
        height_label = QLabel("Height (blocks):")
        height_label.setMinimumWidth(120)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 512)
        self.height_spin.setValue(self.target_height)
        self.height_spin.setSuffix(" blocks")
        height_layout.addWidget(height_label)
        height_layout.addWidget(self.height_spin)
        height_layout.addStretch()
        layout.addLayout(height_layout)
        
        layout.addSpacing(10)
        
        # Performance warning
        warning_label = QLabel(
            "⚠️ <b>Recommendation:</b> Keep the larger dimension at 256 blocks or less for optimal performance."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(
            "QLabel { "
            "background-color: #fff3cd; "
            "color: #856404; "
            "padding: 8px; "
            "border: 1px solid #ffeaa7; "
            "border-radius: 4px; "
            "}"
        )
        layout.addWidget(warning_label)
        
        layout.addSpacing(10)
        
        # Result preview
        self.result_label = QLabel()
        self.result_label.setStyleSheet("QLabel { color: #0066cc; font-weight: bold; }")
        layout.addWidget(self.result_label)
        
        layout.addSpacing(20)
        
        # Info text
        info_text = QLabel(
            "<i>Note: Each block in-game represents one pixel of your image.<br/>"
            "The other dimension adjusts automatically to maintain proportions.</i>"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("QLabel { color: #666; }")
        layout.addWidget(info_text)
        
        layout.addSpacing(20)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.width_radio.toggled.connect(self._on_dimension_changed)
        self.height_radio.toggled.connect(self._on_dimension_changed)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        self.height_spin.valueChanged.connect(self._on_height_changed)
        
        # Set initial state (width is selected by default, so height should be disabled)
        self._on_dimension_changed()
    
    def _on_dimension_changed(self):
        """Handle dimension selection change."""
        if self.width_radio.isChecked():
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(False)
            self._on_width_changed(self.width_spin.value())
        else:
            self.width_spin.setEnabled(False)
            self.height_spin.setEnabled(True)
            self._on_height_changed(self.height_spin.value())
    
    def _on_width_changed(self, value: int):
        """Handle width value change."""
        if self.width_radio.isChecked():
            # Calculate proportional height
            new_height = max(1, round(value / self.aspect_ratio))
            self.height_spin.blockSignals(True)
            self.height_spin.setValue(new_height)
            self.height_spin.blockSignals(False)
            self._update_dimensions()
    
    def _on_height_changed(self, value: int):
        """Handle height value change."""
        if self.height_radio.isChecked():
            # Calculate proportional width
            new_width = max(1, round(value * self.aspect_ratio))
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(new_width)
            self.width_spin.blockSignals(False)
            self._update_dimensions()
    
    def _update_dimensions(self):
        """Update the result dimensions display."""
        width = self.width_spin.value()
        height = self.height_spin.value()
        
        self.target_width = width
        self.target_height = height
        
        self.result_label.setText(
            f"Result: {width} x {height} blocks ({width * height:,} total blocks)"
        )
    
    def get_dimensions(self):
        """Get the selected dimensions.
        
        Returns:
            tuple: (width, height) in blocks
        """
        return (self.target_width, self.target_height)
