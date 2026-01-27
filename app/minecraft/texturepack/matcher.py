from __future__ import annotations


from typing import Iterable, Optional
import math


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
        

    def match_rgb(self, rgb: tuple[int, int, int]) -> BlockTexture:
        raise NotImplementedError("Use match_lab() ou converta RGB para LAB antes")
    

    def match_lab(self, lab: tuple[float, float, float]) -> BlockTexture:
        best_block: Optional[BlockTexture] = None
        best_distance = math.inf

        for block in self.blocks:
            d = self._delta_e(lab, block.lab_color)

            if d < best_distance:
                best_distance = d
                best_block = block
        
        return best_block
    


    @staticmethod
    def _delta_e(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:

        # euclidian distance on LAB color space
        distance = math.sqrt((lab1[0] - lab2[0]) ** 2 + (lab1[1] - lab2[1]) ** 2 + (lab1[2] - lab2[2]) ** 2)

        return distance