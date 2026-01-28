"""
Minepixel Editor - Entry Point
Converts images to Minecraft pixel art with interactive editing.
"""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.application import MinepixelEditorApp


def main():
    """Main entry point for the application."""
    app = MinepixelEditorApp()
    app.setup()
    app.run()


if __name__ == "__main__":
    main()
