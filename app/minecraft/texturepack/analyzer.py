from __future__ import annotations


from pathlib import Path
from typing import Iterable


import numpy as np
from PIL import Image
from skimage import color


from .models import BlockTexture

class TextureAnalyzer:
    def __init__(self, transparency_threshold: float = 0.05):
        """
        Initializes the texture analyzer.
        
        Args:
            transparency_threshold: Minimum ratio of transparent pixels to consider
                                   a texture as having transparency (default: 5%)
        """
        self.transparency_threshold = transparency_threshold
    
    def analyze(self, blocks: Iterable[BlockTexture]) -> None:
        for block in blocks:
            # Detect transparency first
            has_transparency = self._has_transparency(block.texture_path)
            block.has_transparency = has_transparency
            
            # Only compute colors if texture is solid (no transparency)
            if not has_transparency:
                avg_rgb = self._compute_average_rgb(block.texture_path)
                lab = self._rgb_to_lab(avg_rgb)
                block.avg_color = avg_rgb
                block.lab_color = lab
            else:
                # Set to None for transparent textures
                block.avg_color = None
                block.lab_color = None

    
    def _has_transparency(self, texture_path: Path) -> bool:
        """
        Checks if a texture has significant transparency.
        
        Args:
            texture_path: Path to the texture file
            
        Returns:
            True if texture has transparent pixels above threshold, False otherwise
        """
        with Image.open(texture_path) as img:
            img = img.convert("RGBA")
            data = np.array(img)
        
        alpha = data[..., 3]
        total_pixels = alpha.size
        
        # Count pixels with alpha < 255 (transparent or semi-transparent)
        transparent_pixels = np.sum(alpha < 255)
        transparency_ratio = transparent_pixels / total_pixels
        
        return transparency_ratio > self.transparency_threshold
    
    def _compute_average_rgb(self, texture_path: Path) -> tuple[int, int, int]:
        with Image.open(texture_path) as img:
            img = img.convert("RGBA")
            data = np.array(img)

        rgb = data[..., :3]
        alpha = data[..., 3]

        mask = alpha > 0

        if not np.any(mask):
            mean_rgb = rgb.mean(axis=(0, 1))
        else:
            mean_rgb = rgb[mask].mean(axis=0)

        return tuple(int(c) for c in mean_rgb)
    

    def _rgb_to_lab(self, rgb: tuple[int, int, int]) -> tuple[float, float, float]:

        rgb_arr = np.array([[rgb]], dtype=np.float32) / 255.0
        lab_arr = color.rgb2lab(rgb_arr)
        lab = lab_arr[0, 0]
        return float(lab[0]), float(lab[1]), float(lab[2])