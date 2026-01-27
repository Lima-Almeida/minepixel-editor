from __future__ import annotations


from pathlib import Path
from typing import List


from .models import BlockTexture
from .utils import (
iter_block_texture_files,
texture_name_to_block_id,
normalize_block_id,
)

class TexturePackParser:
    def __init__(self, texturepack_root: Path):
        self.texturepack_root = Path(texturepack_root)

    
    def parse(self) -> List[BlockTexture]:
        blocks: List[BlockTexture] = []

        for texture_path in iter_block_texture_files(self.texturepack_root):
            block_id = texture_name_to_block_id(texture_path)
            block_id = normalize_block_id(block_id)

            block = BlockTexture(
                block_id=block_id,
                texture_path=texture_path,
            )

            blocks.append(block)
        
        return blocks