from __future__ import annotations


from pathlib import Path
from typing import List


import numpy as np
from PIL import Image
from skimage import color


from app.minecraft.texturepack.matcher import BlockMatcher
from app.minecraft.texturepack.models import BlockTexture

class ImageToBlockMapper:
    # Number of progress updates per conversion (rows are matched in chunks)
    PROGRESS_STEPS = 20

    def __init__(self, matcher: BlockMatcher):
        self.matcher = matcher


    def map_image(self, image_path: Path, *, target_size: tuple[int, int] | None = None,
                  progress_callback=None) -> List[List[BlockTexture]]:
        """
        Maps an image to Minecraft blocks.

        Args:
            image_path: Path to the image
            target_size: Optional target size (width, height)
            progress_callback: Optional callback function(progress: float) called with 0.0-1.0

        Returns:
            Grid of BlockTexture objects
        """
        with Image.open(image_path) as img:
            img = img.convert("RGB")

            if target_size is not None:
                img = img.resize(target_size, Image.NEAREST)

            return self.map_image_to_blocks(img, progress_callback=progress_callback)

    def map_image_to_blocks(self, img: Image.Image, progress_callback=None) -> List[List[BlockTexture]]:
        """
        Maps a PIL Image to Minecraft blocks.

        Args:
            img: PIL Image (RGB mode)
            progress_callback: Optional callback function(progress: float) called with 0.0-1.0

        Returns:
            Grid of BlockTexture objects
        """
        img = img.convert("RGB")
        rgb = np.array(img)
        rgb_norm = rgb.astype(np.float32) / 255.0
        lab = color.rgb2lab(rgb_norm)

        height, width, _ = lab.shape
        grid: List[List[BlockTexture]] = []

        # Match whole chunks of rows at once (vectorized), reporting progress per chunk
        rows_per_chunk = max(1, -(-height // self.PROGRESS_STEPS))
        for y0 in range(0, height, rows_per_chunk):
            y1 = min(y0 + rows_per_chunk, height)
            blocks = self.matcher.match_lab_array(lab[y0:y1].reshape(-1, 3))
            grid.extend(blocks[i:i + width] for i in range(0, len(blocks), width))

            # Update progress
            if progress_callback:
                progress_callback(y1 / height)

        return grid
