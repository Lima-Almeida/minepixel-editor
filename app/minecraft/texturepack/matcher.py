from __future__ import annotations


from typing import Iterable, List

import numpy as np
from scipy.spatial import cKDTree


from .models import BlockTexture


class BlockMatcher:
    def __init__(self, blocks: Iterable[BlockTexture], allow_transparency: bool = False):
        """
        Initializes the block matcher.

        Args:
            blocks: Iterable of BlockTexture objects
            allow_transparency: If False, ignores blocks with transparency (default: False)
        """
        # Filter blocks: must have LAB color and optionally no transparency
        if allow_transparency:
            self.blocks = [b for b in blocks if b.lab_color is not None]
        else:
            self.blocks = [b for b in blocks if b.lab_color is not None and not b.has_transparency]

        if not self.blocks:
            raise ValueError("No blocks with LAB color available for matching")

        # KD-tree over the blocks' LAB colors. Matching uses Delta-E 76 (euclidean
        # distance in LAB), which is exactly the KD-tree's nearest-neighbor metric
        self._tree = cKDTree(np.array([b.lab_color for b in self.blocks], dtype=np.float64))

    def match_lab_array(self, lab_pixels: np.ndarray) -> List[BlockTexture]:
        """
        Finds the nearest block (Delta-E 76) for many pixels at once.

        Args:
            lab_pixels: Array of shape (N, 3) with LAB colors

        Returns:
            List of N BlockTexture objects (nearest block for each pixel)
        """
        _, indices = self._tree.query(np.asarray(lab_pixels, dtype=np.float64), k=1)
        return [self.blocks[i] for i in indices]
