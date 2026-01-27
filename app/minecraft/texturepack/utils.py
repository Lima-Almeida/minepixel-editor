from __future__ import annotations

from pathlib import Path
from typing import Iterable, Set

VALID_IMAGE_EXTENSIONS = {".png"}

def is_valid_texture_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VALID_IMAGE_EXTENSIONS


def load_ignored_textures(ignored_file: Path = None) -> Set[str]:
    """
    Loads list of textures that should be ignored.
    
    Args:
        ignored_file: Path to ignored textures file.
                     If None, uses data/ignored_textures.txt
    
    Returns:
        Set with names of ignored textures (without extension)
    """
    if ignored_file is None:
        # Try to find file in data/ folder
        project_root = Path(__file__).parent.parent.parent.parent
        ignored_file = project_root / "data" / "ignored_textures.txt"
    
    ignored = set()
    
    if not ignored_file.exists():
        return ignored
    
    with open(ignored_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Ignore empty lines and comments
            if line and not line.startswith('#'):
                ignored.add(line)
    
    return ignored


def should_ignore_texture(texture_path: Path, ignored_textures: Set[str]) -> bool:
    """
    Checks if a texture should be ignored.
    
    Args:
        texture_path: Texture path
        ignored_textures: Set of ignored textures
    
    Returns:
        True if should be ignored, False otherwise
    """
    texture_name = texture_path.stem
    return texture_name in ignored_textures


def get_block_textures_dir(texturepack_root: Path) -> Path:
    """
    Tries to find the block textures directory.
    Supports both resource pack structure and simple folder.
    """
    # Try full resource pack structure first
    block_dir = (
        texturepack_root
        / "assets"
        / "minecraft"
        / "textures"
        / "block"
    )
    
    # If it doesn't exist, assume texturepack_root is already the blocks folder
    if not block_dir.exists():
        block_dir = texturepack_root
    
    if not block_dir.exists() or not block_dir.is_dir():
        raise FileNotFoundError(f"Diretório de texturas de blocos não encontrado: {block_dir}")
    
    return block_dir


def iter_block_texture_files(texturepack_root: Path, ignore_non_blocks: bool = True) -> Iterable[Path]:
    """
    Iterates over block texture files.
    
    Args:
        texturepack_root: Texture pack root directory
        ignore_non_blocks: If True, ignores textures that are not solid blocks
    
    Yields:
        Path of each valid texture
    """
    block_dir = get_block_textures_dir(texturepack_root)
    
    # Load list of ignored textures
    ignored_textures = load_ignored_textures() if ignore_non_blocks else set()

    for path in block_dir.rglob("*"):
        if is_valid_texture_file(path):
            if not should_ignore_texture(path, ignored_textures):
                yield path


def texture_name_to_block_id(texture_path: Path) -> str:
    return f"minecraft:{texture_path.stem}"


def normalize_block_id(block_id: str) -> str:
    if ":" not in block_id:
        return f"minecraft:{block_id}"
    return block_id