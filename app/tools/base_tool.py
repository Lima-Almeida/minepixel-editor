"""
Base Tool class for all editing tools.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from app.ui.canvas_widget import CanvasWidget
    from app.minecraft.texturepack.models import BlockTexture


class BaseTool(ABC):
    """Base class for all editing tools."""
    
    def __init__(self, name: str):
        """
        Initialize the tool.
        
        Args:
            name: Tool name
        """
        self.name = name
        self.is_active = False
    
    @abstractmethod
    def on_mouse_down(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """
        Called when mouse button is pressed.
        
        Args:
            canvas: Canvas widget
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            button: Mouse button ("left" or "right")
        """
        pass
    
    @abstractmethod
    def on_mouse_drag(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """
        Called when mouse is dragged.
        
        Args:
            canvas: Canvas widget
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            button: Mouse button ("left" or "right")
        """
        pass
    
    @abstractmethod
    def on_mouse_up(self, canvas: CanvasWidget, grid_x: int, grid_y: int, button: str) -> None:
        """
        Called when mouse button is released.
        
        Args:
            canvas: Canvas widget
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            button: Mouse button ("left" or "right")
        """
        pass
    
    def activate(self) -> None:
        """Activates this tool."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivates this tool."""
        self.is_active = False
    
    def get_cursor(self) -> str:
        """Returns cursor type for this tool."""
        return "default"
