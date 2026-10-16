"""
Block Management Module
Handles loading, filtering, and managing Minecraft block textures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Set
from collections import defaultdict

from app.minecraft.texturepack.parser import TexturePackParser
from app.minecraft.texturepack.analyzer import TextureAnalyzer
from app.minecraft.texturepack.matcher import BlockMatcher
from app.minecraft.texturepack.utils import load_ignored_textures
from app.minecraft.texturepack.models import BlockTexture


class BlockManager:
    """
    Manages block loading, filtering, and caching.
    """
    
    DIRECTIONAL_SUFFIXES = ['_top', '_side', '_front', '_back', '_bottom', '_end']
    
    def __init__(self, texture_path: Path):
        """
        Initialize block manager.
        
        Args:
            texture_path: Path to Minecraft textures folder
        """
        self.texture_path = texture_path
        self.all_blocks: List[BlockTexture] = []
        self.active_blocks: List[BlockTexture] = []
        self.default_ignored_blocks: Set[str] = load_ignored_textures()
        self.user_ignored_blocks: Set[str] = set()
        self.matcher: BlockMatcher = None
        self._grouped_blocks_cache = None
        self._settings_initialized = False
    
    def load_blocks(self) -> None:
        """Loads all blocks from texture pack."""
        print("[INFO] Loading blocks from texture pack...")
        
        # Parse all blocks (no filtering)
        parser = TexturePackParser(self.texture_path)
        self.all_blocks = parser.parse(ignore_non_blocks=False)
        
        # Filter log_top textures
        original_count = len(self.all_blocks)
        self.all_blocks = [b for b in self.all_blocks if not b.block_id.endswith('_log_top')]
        log_top_filtered = original_count - len(self.all_blocks)
        if log_top_filtered > 0:
            print(f"[DEBUG] Filtered {log_top_filtered} log_top textures")
        
        # Analyze textures for transparency
        print("[DEBUG] Analyzing textures for transparency...")
        analyzer = TextureAnalyzer(transparency_threshold=0.05)
        analyzer.analyze(self.all_blocks)
        transparent_count = sum(1 for b in self.all_blocks if b.has_transparency)
        print(f"[DEBUG] Found {transparent_count} blocks with transparency out of {len(self.all_blocks)}")
        
        # Initialize user ignored blocks, then filter and create the matcher
        if not self._settings_initialized:
            self.user_ignored_blocks = self.default_ignored_bases()
            self._settings_initialized = True
            print(f"[INFO] Initialized with {len(self.user_ignored_blocks)} default ignored blocks")

        self.reload_with_filters()

        print(f"[INFO] Loaded {len(self.all_blocks)} total blocks")
        print(f"[INFO] Using {len(self.active_blocks)} blocks after filters")
        print(f"[INFO] Ignored {len(self.all_blocks) - len(self.active_blocks)} blocks")

    def default_ignored_bases(self) -> Set[str]:
        """
        Computes the default set of ignored base block names, without changing state.

        A base block is ignored when its name or ANY of its variants is listed in
        ignored_textures.txt, or when ANY of its variants has transparency.
        """
        base_to_blocks = defaultdict(list)
        for block in self.all_blocks:
            base_to_blocks[self.get_base_block_name(block.block_id)].append(block)

        ignored = set()
        for base_name, blocks in base_to_blocks.items():
            # ignored_textures.txt lists names without the "minecraft:" prefix
            names = {base_name.split(':')[-1]}
            names.update(b.block_id.split(':')[-1] for b in blocks)

            if names & self.default_ignored_blocks or any(b.has_transparency for b in blocks):
                ignored.add(base_name)

        return ignored

    def set_ignored_blocks(self, base_names: Iterable[str]) -> None:
        """Replaces the ignored base blocks and re-applies filters and matcher."""
        self.user_ignored_blocks = set(base_names)
        self.reload_with_filters()

    def reset_to_defaults(self) -> None:
        """Resets ignored blocks to the default state."""
        self.set_ignored_blocks(self.default_ignored_bases())

    def _apply_filters(self) -> None:
        """Applies current filters to create active_blocks list."""
        self.active_blocks = []
        for block in self.all_blocks:
            base_name = self.get_base_block_name(block.block_id)
            if base_name not in self.user_ignored_blocks:
                self.active_blocks.append(block)

    def reload_with_filters(self) -> None:
        """Re-applies the filters and rebuilds the matcher (None if no block is active)."""
        self._apply_filters()
        self.matcher = (
            BlockMatcher(self.active_blocks, allow_transparency=False)
            if self.active_blocks else None
        )

    @staticmethod
    def get_base_block_name(block_id: str) -> str:
        """Gets the base name of a block by removing directional suffixes."""
        for suffix in BlockManager.DIRECTIONAL_SUFFIXES:
            if block_id.endswith(suffix):
                return block_id[:-len(suffix)]
        return block_id
    
    @staticmethod
    def get_block_variant(block_id: str) -> str:
        """Gets the variant type of a block."""
        for suffix in BlockManager.DIRECTIONAL_SUFFIXES:
            if block_id.endswith(suffix):
                return suffix[1:]  # Remove leading underscore
        return 'normal'
    
    def get_grouped_blocks(self) -> dict:
        """Returns grouped blocks by base name (cached)."""
        if self._grouped_blocks_cache is None:
            print("[DEBUG] Building grouped blocks cache...")
            self._grouped_blocks_cache = defaultdict(lambda: {'variants': [], 'blocks': {}})
            for block in self.all_blocks:
                base_name = self.get_base_block_name(block.block_id)
                variant = self.get_block_variant(block.block_id)
                self._grouped_blocks_cache[base_name]['variants'].append(variant)
                self._grouped_blocks_cache[base_name]['blocks'][variant] = block
            print(f"[DEBUG] Cache built with {len(self._grouped_blocks_cache)} base blocks")
        
        return self._grouped_blocks_cache
