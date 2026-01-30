"""
Main entry point for Minepixel Editor (PySide6 version)
GPU-accelerated Qt interface for Minecraft pixel art creation.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.application import MinepixelEditorApp


def main():
    """Main entry point."""
    print("="*70)
    print("Minepixel Editor - PySide6 Version")
    print("="*70)
    print()
    print("[INFO] Initializing Qt application...")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Minepixel Editor")
    app.setOrganizationName("Minepixel")
    
    print("[INFO] Creating application...")
    
    # Create and setup application
    editor = MinepixelEditorApp()
    editor.setup()
    
    print("[INFO] Application ready!")
    print()
    print("Controls:")
    print("   • Load Image: File menu or Toolbar")
    print("   • Pan: Middle mouse button")
    print("   • Zoom: Mouse scroll wheel")
    print("   • Paint: Left mouse button")
    print("   • Pick Block: Select Picker tool")
    print()
    print("[INFO] Entering main loop...")
    print()
    
    # Run application
    sys.exit(editor.run())


if __name__ == "__main__":
    main()
