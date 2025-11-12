#!/usr/bin/env python3
"""
Dedupit - Preview Generator

Generates large preview images (3000x2000px PNG) with a grid of thumbnails 
from a folder of photos. The generator creates a 10x9 grid (90 slots) with 
260x260 pixel thumbnails, leaving 40 pixels at the top for a header.

The sampling strategy adapts to the number of photos:
- 450+ photos: Samples 1 thumbnail per 5 photos
- 90-449 photos: Distributes photos evenly across all 90 slots
- < 90 photos: Shows all photos, leaving empty slots transparent
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import argparse


class PreviewGenerator:
    """Generates preview images with thumbnails arranged in a grid."""
    
    # Canvas dimensions
    CANVAS_WIDTH = 3000
    CANVAS_HEIGHT = 2000
    
    # Grid configuration
    GRID_COLS = 10
    GRID_ROWS = 9
    THUMBNAIL_SIZE = 260
    HEADER_HEIGHT = 40
    
    # Total slots available
    TOTAL_SLOTS = GRID_COLS * GRID_ROWS  # 90
    
    # Minimum photos threshold for sampling
    MIN_PHOTOS_THRESHOLD = TOTAL_SLOTS * 5  # 450
    
    # Supported image extensions
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    
    def __init__(self, folder_path):
        """
        Initialize the preview generator.
        
        Args:
            folder_path: Path to the folder containing photos
        """
        self.folder_path = Path(folder_path)
        if not self.folder_path.exists():
            raise ValueError(f"Folder does not exist: {folder_path}")
    
    def get_image_files(self):
        """
        Get all image files from the folder.
        
        Returns:
            List of Path objects for image files
        """
        image_files = []
        for file in self.folder_path.iterdir():
            if file.is_file() and file.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                image_files.append(file)
        return sorted(image_files)
    
    def calculate_sampling(self, total_photos):
        """
        Calculate how many photos to sample based on total count.
        
        Args:
            total_photos: Total number of photos in the folder
            
        Returns:
            Tuple of (number_of_thumbnails, sample_interval)
        """
        if total_photos >= self.MIN_PHOTOS_THRESHOLD:
            # Sample 1 thumbnail per 5 photos
            num_thumbnails = self.TOTAL_SLOTS
            sample_interval = 5
        elif total_photos > self.TOTAL_SLOTS:
            # Sample to fill all 90 slots
            num_thumbnails = self.TOTAL_SLOTS
            sample_interval = total_photos / self.TOTAL_SLOTS
        else:
            # Show all photos, leave empty slots transparent
            num_thumbnails = total_photos
            sample_interval = 1
        
        return num_thumbnails, sample_interval
    
    def sample_images(self, image_files):
        """
        Sample images according to the sampling rules.
        
        Args:
            image_files: List of image file paths
            
        Returns:
            List of sampled image paths
        """
        total_photos = len(image_files)
        num_thumbnails, sample_interval = self.calculate_sampling(total_photos)
        
        sampled = []
        if sample_interval == 1:
            # Take all photos
            sampled = image_files[:num_thumbnails]
        else:
            # Sample at intervals
            for i in range(num_thumbnails):
                index = int(i * sample_interval)
                if index < len(image_files):
                    sampled.append(image_files[index])
        
        return sampled
    
    def create_thumbnail(self, image_path):
        """
        Create a thumbnail from an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            PIL Image object of the thumbnail
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                # Create thumbnail maintaining aspect ratio
                img.thumbnail((self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
                
                # Create a square thumbnail with padding
                thumb = Image.new('RGB', (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE), (0, 0, 0))
                
                # Center the image
                x = (self.THUMBNAIL_SIZE - img.width) // 2
                y = (self.THUMBNAIL_SIZE - img.height) // 2
                thumb.paste(img, (x, y))
                
                return thumb
        except Exception as e:
            print(f"Error creating thumbnail for {image_path}: {e}", file=sys.stderr)
            # Return a black square on error
            return Image.new('RGB', (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE), (0, 0, 0))
    
    def calculate_grid_positions(self):
        """
        Calculate the positions for thumbnails in the grid.
        
        Returns:
            List of (x, y) tuples for each grid position
        """
        positions = []
        
        # Calculate spacing to distribute thumbnails evenly
        # Available space after header
        available_height = self.CANVAS_HEIGHT - self.HEADER_HEIGHT
        
        # Calculate the total space needed and available space for margins
        total_thumb_width = self.GRID_COLS * self.THUMBNAIL_SIZE
        total_thumb_height = self.GRID_ROWS * self.THUMBNAIL_SIZE
        
        # Calculate spacing (can be negative if thumbnails don't fit - they'll overlap)
        # We use GRID_COLS + 1 gaps horizontally and GRID_ROWS + 1 gaps vertically
        horizontal_spacing = (self.CANVAS_WIDTH - total_thumb_width) / (self.GRID_COLS + 1)
        vertical_spacing = (available_height - total_thumb_height) / (self.GRID_ROWS + 1)
        
        for row in range(self.GRID_ROWS):
            for col in range(self.GRID_COLS):
                # Position starts with margin, then adds thumbnail size and spacing
                x = int(horizontal_spacing * (col + 1) + self.THUMBNAIL_SIZE * col)
                # Ensure y is at least HEADER_HEIGHT
                y = int(max(self.HEADER_HEIGHT, self.HEADER_HEIGHT + vertical_spacing * (row + 1) + self.THUMBNAIL_SIZE * row))
                positions.append((x, y))
        
        return positions
    
    def generate_preview(self, output_path=None):
        """
        Generate the preview image.
        
        Args:
            output_path: Path where to save the preview image. If None, saves in the folder.
            
        Returns:
            Path to the generated preview image
        """
        # Get and sample images
        image_files = self.get_image_files()
        if not image_files:
            raise ValueError(f"No image files found in {self.folder_path}")
        
        sampled_images = self.sample_images(image_files)
        
        print(f"Found {len(image_files)} images, sampling {len(sampled_images)} for preview")
        
        # Create canvas with transparency
        canvas = Image.new('RGBA', (self.CANVAS_WIDTH, self.CANVAS_HEIGHT), (255, 255, 255, 0))
        
        # Calculate grid positions
        positions = self.calculate_grid_positions()
        
        # Place thumbnails on canvas
        for i, image_path in enumerate(sampled_images):
            if i >= len(positions):
                break
            
            print(f"Processing {i+1}/{len(sampled_images)}: {image_path.name}")
            thumbnail = self.create_thumbnail(image_path)
            
            # Convert thumbnail to RGBA for proper pasting
            if thumbnail.mode != 'RGBA':
                thumbnail = thumbnail.convert('RGBA')
            
            x, y = positions[i]
            canvas.paste(thumbnail, (x, y), thumbnail)
        
        # Determine output path
        if output_path is None:
            output_path = self.folder_path / 'preview.png'
        else:
            output_path = Path(output_path)
        
        # Save the preview
        canvas.save(output_path, 'PNG')
        print(f"Preview saved to: {output_path}")
        
        return output_path


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Generate a large preview image from a folder of photos.'
    )
    parser.add_argument(
        'folder',
        help='Path to the folder containing photos'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output path for the preview image (default: preview.png in the folder)'
    )
    
    args = parser.parse_args()
    
    try:
        generator = PreviewGenerator(args.folder)
        generator.generate_preview(args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
