# Minepixel Editor

Image editor with the special functionality of converting any image into **Minecraft block pixel art**.

## Quick Start

```bash
python setup_and_run.py
```

The script will automatically:
- Create a virtual environment
- Install all dependencies
- Run the application

Works on Windows, Linux, and macOS

## Running Tests

With the virtual environment active:

```bash
pip install -r requirements-dev.txt
pytest
```

## Features

- Image conversion to pixel art using Minecraft blocks, with the size chosen on import (up to 512×512 blocks)
- Block-based editing as if they were pixels: brush (sizes 1 to 15) and eyedropper
- Intelligent color matching using LAB (CIELAB) color space, with fast KD-tree search
- Block filter: choose which blocks can be used (transparent and non-solid blocks are excluded by default)
- Material list export (TXT), grouped by block and sorted by quantity
- High-resolution PNG export (16 px per block)
- Optional visual grid to visualize blocks
- Texture caching for optimized performance

## Project Status

```
Rendering            ████████████████████ 100% 
Image Conversion     ████████████████████ 100% 
Color Matching       ████████████████████ 100% 
Basic Editing        █████████████████░░░ 80% 
Graphical Interface  █████████████░░░░░░░ 60% 
Tools                ████░░░░░░░░░░░░░░░░ 20% 
Cache/Persistence    ████░░░░░░░░░░░░░░░░ 20% 
```

## How It Works

### 1. Conversion Pipeline

```
Original Image
     ↓
[ImageToBlockMapper] - Converts each pixel
     ↓
Block Grid (2D)
     ↓
[BlockRenderer] - Renders with textures (PNG export)
     ↓
Final Pixel Art
```

### 2. Color Matching

```python
# Once, when the app starts:
1. Compute each block texture's average color and convert it to LAB
2. Index the block colors in a KD-tree

# For each image:
1. Convert all pixels from RGB to LAB (perceptual color space)
2. Find the block with the smallest Delta-E 76 distance (nearest neighbor in the KD-tree)
3. Place it in the grid
```

Delta-E 76 is the euclidean distance in LAB, which is what makes the KD-tree search possible.

### 3. Rendering

```python
# For each block in the grid:
1. Load block texture (with caching)
2. Resize to desired size
3. Paste at correct position in final image
4. (Optional) Draw grid lines
```

## Next Steps

Implement basic tools and improve rendering efficience:
1. Undo/Redo
2. Other export types (.schematic, custom extension, etc)
3. Building guide
4. Improve UI/UX
5. Improve rendering efficiency

