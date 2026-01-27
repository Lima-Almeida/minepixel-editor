from __future__ import annotations


from pathlib import Path
from typing import List


import numpy as np
from PIL import Image
from skimage import color


from app.minecraft.texturepack.matcher import BlockMatcher
from app.minecraft.texturepack.models import BlockTexture

class ImageToBlockMapper:
    def __init__(self, matcher: BlockMatcher):
        self.matcher = matcher

    
    def map_image(self, image_path: Path, *, target_size: tuple[int, int] | None = None) -> List[List[BlockTexture]]:

        with Image.open(image_path) as img:
            img = img.convert("RGB")

            if target_size is not None:
                img = img.resize(target_size, Image.NEAREST)
            
            rgb = np.array(img)

        rgb_norm = rgb.astype(np.float32) / 255.0
        lab = color.rgb2lab(rgb_norm)

        height, width, _ = lab.shape

        grid: List[List[BlockTexture]] = []

        for y in range(height):
            row: List[BlockTexture] = []
            for x in range(width):
                pixel_lab = tuple(lab[y, x])
                block = self.matcher.match_lab(pixel_lab)
                row.append(block)
            grid.append(row)
        
        return grid