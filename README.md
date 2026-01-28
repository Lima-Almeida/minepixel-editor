# Minepixel Editor

Image editor with the special functionality of converting any image into **Minecraft block pixel art**.

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
Tools                ░░░░░░░░░░░░░░░░░░░░ 0% 
Cache/Persistence    ████░░░░░░░░░░░░░░░░ 20% 
```


## Architecture

```
app/
├── core/
│   └── renderer.py          # Renders block grid to image
├── minecraft/
│   ├── image_mapper.py      # Converts image to block grid
│   └── texturepack/
│       ├── models.py        # Data model (BlockTexture)
│       ├── parser.py        # Loads Minecraft textures
│       ├── analyzer.py      # Calculates average colors (RGB to LAB)
│       ├── matcher.py       # Finds best block by color
│       └── utils.py         # Helper functions

assets/
└── minecraft_textures/
    └── blocks/              # Block PNG textures (16x16)

data/
└── blocks.json             # Block analysis cache
└── ignored_textures.txt    # Manual texture filter list

output/                     # Generated images
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
1. Brush, eraser, fill, eyedropper, etc.
2. Undo/Redo
3. Other export types (.schematic, custom extension, etc)
4. Improve UI/UX
5. Improve rendering efficience
6. Building guide

