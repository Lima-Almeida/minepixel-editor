from __future__ import annotations


from pathlib import Path
from typing import List, Optional, Tuple


import numpy as np
from PIL import Image


from app.minecraft.texturepack.models import BlockTexture


class BlockRenderer:
    """
    Renders a grid of Minecraft blocks into a pixel art image.
    Each block is represented by its complete texture.
    """
    
    def __init__(self, block_size: int = 16):
        """
        Initializes the renderer.
        
        Args:
            block_size: Size in pixels of each block (default: 16x16)
        """
        self.block_size = block_size
        self._texture_cache: dict[str, Image.Image] = {}
    
    def render(
        self, 
        block_grid: List[List[BlockTexture]], 
        output_path: Optional[Path] = None
    ) -> Image.Image:
        """
        Renders a grid of blocks into an image.
        
        Args:
            block_grid: 2D grid of BlockTexture (height x width)
            output_path: Optional path to save the image
            
        Returns:
            Rendered PIL Image
        """
        if not block_grid or not block_grid[0]:
            raise ValueError("Empty block grid")
        
        height = len(block_grid)
        width = len(block_grid[0])
        
        # Create destination image
        output_width = width * self.block_size
        output_height = height * self.block_size
        output_image = Image.new('RGBA', (output_width, output_height), (255, 255, 255, 255))
        
        # Render each block
        for y in range(height):
            for x in range(width):
                block = block_grid[y][x]
                texture = self._load_texture(block)
                
                # Position where to paste the texture
                paste_x = x * self.block_size
                paste_y = y * self.block_size
                
                output_image.paste(texture, (paste_x, paste_y), texture)
        
        # Save if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_image.save(output_path)
        
        return output_image
    
    def render_with_grid(
        self,
        block_grid: List[List[BlockTexture]],
        output_path: Optional[Path] = None,
        grid_color: Tuple[int, int, int, int] = (128, 128, 128, 128)
    ) -> Image.Image:
        """
        Renders the image with visible grid lines between blocks.
        
        Args:
            block_grid: 2D grid of BlockTexture
            output_path: Optional path to save
            grid_color: RGBA color of grid lines
            
        Returns:
            Rendered PIL Image with grid
        """
        # Render base image
        image = self.render(block_grid, output_path=None)
        
        # Add grid lines
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image, 'RGBA')
        
        height = len(block_grid)
        width = len(block_grid[0])
        
        # Vertical lines
        for x in range(width + 1):
            x_pos = x * self.block_size
            draw.line(
                [(x_pos, 0), (x_pos, height * self.block_size)],
                fill=grid_color,
                width=1
            )
        
        # Horizontal lines
        for y in range(height + 1):
            y_pos = y * self.block_size
            draw.line(
                [(0, y_pos), (width * self.block_size, y_pos)],
                fill=grid_color,
                width=1
            )
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
        
        return image
    
    def render_preview(
        self,
        block_grid: List[List[BlockTexture]],
        max_size: Tuple[int, int] = (800, 600)
    ) -> Image.Image:
        """
        Renders a resized preview of the image for quick visualization.
        
        Args:
            block_grid: 2D grid of BlockTexture
            max_size: Maximum preview size (width, height)
            
        Returns:
            Resized PIL Image
        """
        image = self.render(block_grid)
        
        # Calculate proportion maintaining aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        return image
    
    def get_block_at_position(
        self,
        block_grid: List[List[BlockTexture]],
        pixel_x: int,
        pixel_y: int
    ) -> Optional[Tuple[int, int, BlockTexture]]:
        """
        Returns the block at a pixel position in the rendered image.
        
        Args:
            block_grid: Block grid
            pixel_x: Pixel X coordinate
            pixel_y: Pixel Y coordinate
            
        Returns:
            Tuple (grid_x, grid_y, BlockTexture) or None if out of bounds
        """
        grid_x = pixel_x // self.block_size
        grid_y = pixel_y // self.block_size
        
        if 0 <= grid_y < len(block_grid) and 0 <= grid_x < len(block_grid[0]):
            return (grid_x, grid_y, block_grid[grid_y][grid_x])
        
        return None
    
    def replace_block(
        self,
        block_grid: List[List[BlockTexture]],
        grid_x: int,
        grid_y: int,
        new_block: BlockTexture
    ) -> bool:
        """
        Replaces a block in the grid (for brush functionality).
        
        Args:
            block_grid: Block grid (modified in-place)
            grid_x: X coordinate in grid
            grid_y: Y coordinate in grid
            new_block: New block to place
            
        Returns:
            True if replacement was successful, False otherwise
        """
        if 0 <= grid_y < len(block_grid) and 0 <= grid_x < len(block_grid[0]):
            block_grid[grid_y][grid_x] = new_block
            return True
        
        return False
    
    def _load_texture(self, block: BlockTexture) -> Image.Image:
        """
        Loads and caches a block's texture.
        
        Args:
            block: BlockTexture with texture_path
            
        Returns:
            PIL Image of the texture
        """
        cache_key = str(block.texture_path)
        
        if cache_key not in self._texture_cache:
            texture = Image.open(block.texture_path).convert('RGBA')
            
            # Resize to standard size if necessary
            if texture.size != (self.block_size, self.block_size):
                texture = texture.resize(
                    (self.block_size, self.block_size),
                    Image.Resampling.NEAREST
                )
            
            self._texture_cache[cache_key] = texture
        
        return self._texture_cache[cache_key]
    
    def clear_cache(self) -> None:
        """Clears texture cache to free memory."""
        self._texture_cache.clear()