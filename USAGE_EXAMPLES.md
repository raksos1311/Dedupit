# Usage Examples

## Basic Usage

Generate a preview in the same folder as the photos:

```bash
python3 preview_generator.py /path/to/photos
```

This creates `preview.png` in the photos folder.

## Custom Output Location

Specify a custom output path:

```bash
python3 preview_generator.py /path/to/photos -o /path/to/output/custom_preview.png
```

## Behavior Examples

### Scenario 1: Few Photos (< 90)
When you have fewer than 90 photos, all photos are displayed:

```bash
# With 50 photos
python3 preview_generator.py /photos/vacation
# Output: Shows all 50 photos, leaving 40 slots transparent
```

### Scenario 2: Medium Collection (90-449 photos)
Photos are evenly distributed across all 90 slots:

```bash
# With 180 photos
python3 preview_generator.py /photos/events
# Output: Shows 90 photos, sampling every ~2 photos
```

### Scenario 3: Large Collection (450+ photos)
Samples 1 photo per every 5 photos:

```bash
# With 500 photos
python3 preview_generator.py /photos/archive
# Output: Shows 90 photos, sampling every 5th photo
```

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)

## Output Specifications

- **Canvas Size**: 3000×2000 pixels
- **Format**: PNG with transparency (RGBA)
- **Grid**: 10 columns × 9 rows = 90 slots
- **Thumbnail Size**: 260×260 pixels each
- **Header Space**: 40 pixels at top
- **Spacing**: Evenly distributed across canvas

## Performance Notes

Processing time depends on:
- Number of photos to sample
- Original image sizes
- Disk I/O speed

Typical processing times:
- 50 photos: ~2-5 seconds
- 100 photos: ~3-7 seconds
- 500 photos: ~5-10 seconds
