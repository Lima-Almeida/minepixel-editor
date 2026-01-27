"""
Converts any image from the 'input' folder to Minecraft pixel art.
Place an image in the 'input' folder and run this script.
"""

from pathlib import Path
from app.minecraft.texturepack.parser import TexturePackParser
from app.minecraft.texturepack.analyzer import TextureAnalyzer
from app.minecraft.texturepack.matcher import BlockMatcher
from app.minecraft.image_mapper import ImageToBlockMapper
from app.core.renderer import BlockRenderer


def find_input_image(input_dir: Path) -> Path:
    """
    Finds the first valid image in the input folder.
    
    Args:
        input_dir: Input directory
        
    Returns:
        Path of the found image
        
    Raises:
        FileNotFoundError: If no image is found
    """
    valid_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
    
    for ext in valid_extensions:
        images = list(input_dir.glob(f'*{ext}'))
        if images:
            return images[0]
    
    raise FileNotFoundError(
        f"No image found in: {input_dir}\n"
        f"Supported formats: {', '.join(valid_extensions)}"
    )


def main():
    print("=" * 70)
    print("MINEPIXEL EDITOR - Automatic Conversion to Minecraft Pixel Art")
    print("=" * 70)
    print()
    
    # Paths
    input_dir = Path("input")
    texture_pack_path = Path("assets/minecraft_textures/blocks")
    output_dir = Path("output")
    
    # Ensure folders exist
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    # Search for input image
    print("Searching for image in 'input' folder...")
    try:
        input_image = find_input_image(input_dir)
        print(f"   [OK] Image found: {input_image.name}")
    except FileNotFoundError as e:
        print(f"   [ERROR] {e}")
        print()
        print("Tip: Place an image (PNG, JPG, etc.) in the 'input' folder")
        return
    
    # Read image information
    from PIL import Image
    with Image.open(input_image) as img:
        original_width, original_height = img.size
        mode = img.mode
    
    print(f"   Dimensions: {original_width}x{original_height} pixels")
    print(f"   Mode: {mode}")
    print()
    
    # Define output names based on input name
    output_name = input_image.stem
    output_basic = output_dir / f"{output_name}_minecraft.png"
    output_grid = output_dir / f"{output_name}_minecraft_grid.png"
    
    # Verify textures
    if not texture_pack_path.exists():
        print(f"WARNING: Texture folder not found: {texture_pack_path}")
        print(f"   Please configure textures following ASSETS_SETUP.md")
        print()
        texture_pack_path.mkdir(parents=True, exist_ok=True)
        print(f"   [OK] Folders created")
        print()
        print(f"[ERROR] Cannot continue without textures.")
        print(f"   Copy Minecraft texture PNG files to:")
        print(f"   {texture_pack_path.absolute()}")
        return
    
    png_files = list(texture_pack_path.glob("*.png"))
    if len(png_files) == 0:
        print(f"WARNING: No PNG textures found in: {texture_pack_path}")
        print(f"   Please copy Minecraft block PNG textures (16x16)")
        print(f"   to the folder: {texture_pack_path.absolute()}")
        print()
        print(f"[ERROR] Cannot continue without textures.")
        return
    
    # 1. Parse texture pack
    print("Step 1/5: Loading Minecraft textures...")
    try:
        parser = TexturePackParser(texture_pack_path)
        blocks = parser.parse()
        print(f"   [OK] {len(blocks)} textures loaded")
        print(f"   [INFO] Manual filters applied (see data/ignored_textures.txt)")
    except Exception as e:
        print(f"   [ERROR] Error loading textures: {e}")
        return
    
    print()
    
    # 2. Analyze textures
    print("Step 2/5: Analyzing texture colors...")
    try:
        analyzer = TextureAnalyzer(transparency_threshold=0.05)
        analyzer.analyze(blocks)
        
        # Count blocks with transparency
        transparent_count = sum(1 for b in blocks if b.has_transparency)
        solid_count = len(blocks) - transparent_count
        
        print(f"   [OK] Colors analyzed (RGB to LAB)")
        print(f"   [OK] Solid blocks: {solid_count}")
        print(f"   [OK] Transparent blocks auto-filtered: {transparent_count}")
    except Exception as e:
        print(f"   [ERROR] Error analyzing colors: {e}")
        return
    
    print()
    
    # 3. Create matcher
    print("Step 3/5: Creating color matching system...")
    try:
        matcher = BlockMatcher(blocks, allow_transparency=False)
        print(f"   [OK] Matching system created with {len(matcher.blocks)} usable blocks")
        print(f"   [INFO] Only solid blocks without transparency are used")
    except Exception as e:
        print(f"   [ERROR] Error creating matcher: {e}")
        return
    
    print()
    
    # 4. Map image
    print("Step 4/5: Converting image to blocks...")
    print(f"   Processing {original_width * original_height:,} pixels...")
    try:
        mapper = ImageToBlockMapper(matcher)
        # Each pixel of the original image becomes a block (no resizing)
        block_grid = mapper.map_image(input_image, target_size=None)
        height = len(block_grid)
        width = len(block_grid[0])
        print(f"   [OK] Grid of {width}x{height} blocks created")
        print(f"   [OK] Total of {width * height:,} blocks")
        print(f"   [OK] Each original pixel = 1 block of 16x16")
    except Exception as e:
        print(f"   [ERROR] Error mapping image: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # 5. Render result
    print("Step 5/5: Rendering pixel art...")
    final_width = width * 16
    final_height = height * 16
    print(f"   Final size: {final_width}x{final_height} pixels")
    
    try:
        renderer = BlockRenderer(block_size=16)
        
        # Basic rendering
        print(f"   Rendering basic version...")
        output_image = renderer.render(block_grid, output_basic)
        print(f"   [OK] Saved to: {output_basic}")
        
        # Grid rendering
        print(f"   Rendering version with grid...")
        grid_image = renderer.render_with_grid(block_grid, output_grid)
        print(f"   [OK] Saved to: {output_grid}")
    except Exception as e:
        print(f"   [ERROR] Error rendering: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 70)
    print("CONVERSION COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print(f"Generated files:")
    print(f"   - {output_basic.name} - Basic version")
    print(f"   - {output_grid.name} - With grid lines")
    print()
    print(f"Tip: Open the images in the 'output' folder to see the result!")
    print(f"Tip: To convert another image, replace the file in the 'input' folder")
    print()
    
    # Statistics
    file_size_mb = output_basic.stat().st_size / (1024 * 1024)
    print(f"Statistics:")
    print(f"   - File size: {file_size_mb:.2f} MB")
    
    # Count blocks and their quantities
    from collections import Counter
    block_counts = Counter()
    for row in block_grid:
        for block in row:
            block_counts[block.block_id] += 1
    
    unique_count = len(block_counts)
    print(f"   - Unique blocks used: {unique_count} out of {len(blocks)} available")
    print()
    
    # List blocks sorted by quantity (most used first)
    print("Blocks used in the conversion (sorted by quantity):")
    print("=" * 70)
    for block_id, count in block_counts.most_common():
        percentage = (count / (width * height)) * 100
        print(f"   {block_id:40s} : {count:6,} blocks ({percentage:5.2f}%)")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
