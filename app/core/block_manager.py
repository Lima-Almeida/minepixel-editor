"""
Block Management Module
Handles loading, filtering, and managing Minecraft block textures.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Set
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
        
        # Initialize user ignored blocks
        if not self._settings_initialized:
            self._initialize_user_ignored_blocks()
            self._settings_initialized = True
        
        # Filter user-ignored blocks
        self._apply_filters()
        
        print(f"[INFO] Loaded {len(self.all_blocks)} total blocks")
        print(f"[INFO] Using {len(self.active_blocks)} blocks after filters")
        print(f"[INFO] Ignored {len(self.all_blocks) - len(self.active_blocks)} blocks")
        
        # Create matcher
        if self.active_blocks:
            self.matcher = BlockMatcher(self.active_blocks, allow_transparency=False)
    
    def _initialize_user_ignored_blocks(self) -> None:
        """Initialize user_ignored_blocks with default ignored textures and transparent blocks."""
        if not self.all_blocks:
            print("[WARNING] Cannot initialize ignored blocks - no blocks loaded yet")
            return
        
        # Group blocks to get base names and their variants
        all_base_names = set()
        base_to_variants = defaultdict(set)
        base_to_blocks = defaultdict(list)
        
        for block in self.all_blocks:
            base_name = self.get_base_block_name(block.block_id)
            all_base_names.add(base_name)
            texture_name = block.block_id.split(':')[-1] if ':' in block.block_id else block.block_id
            base_to_variants[base_name].add(texture_name)
            base_to_blocks[base_name].append(block)
        
        print(f"[DEBUG] Found {len(all_base_names)} unique base names in loaded blocks")
        print(f"[DEBUG] Default ignored list has {len(self.default_ignored_blocks)} entries")
        
        matched_count = 0
        transparency_count = 0
        
        for base_name in all_base_names:
            name_without_prefix = base_name.split(':')[-1] if ':' in base_name else base_name
            
            # Check if base name itself is in ignored list
            if name_without_prefix in self.default_ignored_blocks:
                self.user_ignored_blocks.add(base_name)
                matched_count += 1
                continue
            
            # Check if ANY of the variants are in ignored list
            variants = base_to_variants[base_name]
            variant_matched = False
            for variant in variants:
                if variant in self.default_ignored_blocks:
                    self.user_ignored_blocks.add(base_name)
                    matched_count += 1
                    variant_matched = True
                    break
            
            if variant_matched:
                continue
            
            # Check if ANY variant has transparency
            blocks_for_base = base_to_blocks[base_name]
            for block in blocks_for_base:
                if block.has_transparency:
                    self.user_ignored_blocks.add(base_name)
                    transparency_count += 1
                    break
        
        print(f"[INFO] Initialized with {len(self.user_ignored_blocks)} default ignored blocks:")
        print(f"       - {matched_count} matched from ignored_textures.txt")
        print(f"       - {transparency_count} blocks with transparency")
    
    def _apply_filters(self) -> None:
        """Applies current filters to create active_blocks list."""
        self.active_blocks = []
        for block in self.all_blocks:
            base_name = self.get_base_block_name(block.block_id)
            if base_name not in self.user_ignored_blocks:
                self.active_blocks.append(block)
    
    def is_block_ignored(self, base_name: str) -> bool:
        """Check if a block is ignored."""
        return base_name in self.user_ignored_blocks
    
    def toggle_block_ignore(self, base_name: str, is_ignored: bool) -> None:
        """Toggle ignore state for a block."""
        if is_ignored:
            self.user_ignored_blocks.add(base_name)
        else:
            self.user_ignored_blocks.discard(base_name)
    
    def reset_to_defaults(self) -> None:
        """Resets ignored blocks to default state."""
        self.user_ignored_blocks.clear()
        self._initialize_user_ignored_blocks()
        self._apply_filters()
    
    def reload_with_filters(self) -> None:
        """Reloads blocks with current filter settings."""
        self._apply_filters()
        if self.active_blocks:
            self.matcher = BlockMatcher(self.active_blocks, allow_transparency=False)
    
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
