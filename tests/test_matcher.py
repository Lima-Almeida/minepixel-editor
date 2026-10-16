"""
Tests for BlockMatcher and ImageToBlockMapper.

The KD-tree matcher is checked against a plain linear search using Delta-E 76,
the original matching algorithm of the project.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage import color

from app.minecraft.image_mapper import ImageToBlockMapper
from app.minecraft.texturepack.matcher import BlockMatcher
from app.minecraft.texturepack.models import BlockTexture


# ---------- reference implementation (original linear search) ----------

def delta_e(lab1, lab2) -> float:
    """Delta-E 76: euclidean distance in LAB color space."""
    return math.sqrt((lab1[0] - lab2[0]) ** 2 + (lab1[1] - lab2[1]) ** 2 + (lab1[2] - lab2[2]) ** 2)


def linear_search_distance(lab, blocks) -> float:
    """Smallest Delta-E 76 from a color to any of the blocks."""
    return min(delta_e(lab, b.lab_color) for b in blocks)


# ---------- helpers ----------

def make_block(name: str, lab, transparent: bool = False) -> BlockTexture:
    return BlockTexture(
        block_id=f"minecraft:{name}",
        texture_path=Path(f"{name}.png"),
        lab_color=tuple(float(c) for c in lab),
        has_transparency=transparent,
    )


def random_blocks(rng: np.random.Generator, count: int):
    labs = np.column_stack([
        rng.uniform(0, 100, count),     # L
        rng.uniform(-100, 100, count),  # a
        rng.uniform(-100, 100, count),  # b
    ])
    return [make_block(f"block_{i}", lab) for i, lab in enumerate(labs)]


# ---------- BlockMatcher ----------

def test_kdtree_finds_the_same_nearest_distance_as_linear_search():
    rng = np.random.default_rng(42)
    blocks = random_blocks(rng, 250)
    pixels = np.column_stack([
        rng.uniform(0, 100, 2000),
        rng.uniform(-100, 100, 2000),
        rng.uniform(-100, 100, 2000),
    ])

    matched = BlockMatcher(blocks).match_lab_array(pixels)

    # Compare distances, not identities: blocks with identical colors are equally valid
    for lab, block in zip(pixels, matched):
        assert delta_e(lab, block.lab_color) == pytest.approx(linear_search_distance(lab, blocks), abs=1e-9)


def test_block_color_matches_itself():
    blocks = random_blocks(np.random.default_rng(7), 50)
    matcher = BlockMatcher(blocks)

    matched = matcher.match_lab_array(np.array([b.lab_color for b in blocks]))

    assert [b.block_id for b in matched] == [b.block_id for b in blocks]


def test_transparent_blocks_are_ignored_by_default():
    solid = make_block("stone", (50, 0, 0))
    glass = make_block("glass", (90, 0, 0), transparent=True)

    matched = BlockMatcher([solid, glass]).match_lab_array(np.array([[90.0, 0.0, 0.0]]))

    assert matched[0].block_id == "minecraft:stone"


def test_transparent_blocks_are_used_when_allowed():
    solid = make_block("stone", (50, 0, 0))
    glass = make_block("glass", (90, 0, 0), transparent=True)

    matcher = BlockMatcher([solid, glass], allow_transparency=True)
    matched = matcher.match_lab_array(np.array([[90.0, 0.0, 0.0]]))

    assert matched[0].block_id == "minecraft:glass"


def test_raises_without_usable_blocks():
    no_color = BlockTexture(block_id="minecraft:air", texture_path=Path("air.png"))

    with pytest.raises(ValueError):
        BlockMatcher([no_color])


# ---------- ImageToBlockMapper ----------

def lab_blocks_for_image():
    """A small palette spread over the LAB space."""
    return random_blocks(np.random.default_rng(3), 40)


def random_image(width: int, height: int) -> Image.Image:
    pixels = np.random.default_rng(1).integers(0, 256, (height, width, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


def test_mapper_matches_linear_search_on_an_image():
    blocks = lab_blocks_for_image()
    img = random_image(23, 17)
    lab = color.rgb2lab(np.asarray(img).astype(np.float32) / 255.0)

    grid = ImageToBlockMapper(BlockMatcher(blocks)).map_image_to_blocks(img)

    for y in range(17):
        for x in range(23):
            assert delta_e(lab[y, x], grid[y][x].lab_color) == pytest.approx(
                linear_search_distance(lab[y, x], blocks), abs=1e-6
            )


@pytest.mark.parametrize("width, height", [(1, 1), (7, 5), (5, 64), (64, 3)])
def test_mapper_grid_shape(width, height):
    grid = ImageToBlockMapper(BlockMatcher(lab_blocks_for_image())).map_image_to_blocks(
        random_image(width, height)
    )

    assert len(grid) == height
    assert all(len(row) == width for row in grid)


def test_mapper_reports_progress_up_to_one():
    progress = []

    ImageToBlockMapper(BlockMatcher(lab_blocks_for_image())).map_image_to_blocks(
        random_image(30, 100), progress_callback=progress.append
    )

    assert progress == sorted(progress)
    assert progress[-1] == 1.0
    assert len(progress) <= ImageToBlockMapper.PROGRESS_STEPS
