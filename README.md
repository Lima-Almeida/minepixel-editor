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

Works on Windows, Linux, and macOS!

## Features

- Image conversion to pixel art using Minecraft blocks
- Block-based editing as if they were pixels (block brush)
- Intelligent color matching using LAB (CIELAB) color space
- Optional visual grid to visualize blocks
- High-resolution image export
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
[BlockRenderer] - Renders with textures
     ↓
Final Pixel Art
```

### 2. Color Matching

```python
# For each pixel in the image:
1. Convert RGB to LAB (perceptual color space)
2. Calculate Delta-E distance for all blocks
3. Select block with smallest distance
4. Place in grid
```

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
5. Improve rendering efficience

