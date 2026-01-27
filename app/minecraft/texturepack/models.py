from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple

RGB = Tuple[int, int, int]
LAB = Tuple[float, float, float]

@dataclass
class BlockTexture:

    block_id: str
    texture_path: Path

    avg_color: Optional[RGB] = None
    lab_color: Optional[LAB] = None

    texture_size: Optional[Tuple[int, int]] = None
    has_transparency: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["texture_path"] = str(self.texture_path)
        return data