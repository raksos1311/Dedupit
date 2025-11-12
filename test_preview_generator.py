#!/usr/bin/env python3
"""
Unit tests for the preview generator.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from PIL import Image
from preview_generator import PreviewGenerator


class TestPreviewGenerator(unittest.TestCase):
    """Test cases for PreviewGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    def create_test_images(self, count):
        """Create test images in the test directory."""
        for i in range(count):
            img = Image.new('RGB', (100, 100), color=(i % 255, (i * 2) % 255, (i * 3) % 255))
            img.save(self.test_path / f'test_{i:03d}.jpg', 'JPEG')
    
    def test_canvas_dimensions(self):
        """Test that canvas has correct dimensions."""
        self.assertEqual(PreviewGenerator.CANVAS_WIDTH, 3000)
        self.assertEqual(PreviewGenerator.CANVAS_HEIGHT, 2000)
    
    def test_grid_configuration(self):
        """Test grid configuration."""
        self.assertEqual(PreviewGenerator.GRID_COLS, 10)
        self.assertEqual(PreviewGenerator.GRID_ROWS, 9)
        self.assertEqual(PreviewGenerator.TOTAL_SLOTS, 90)
    
    def test_thumbnail_size(self):
        """Test thumbnail size."""
        self.assertEqual(PreviewGenerator.THUMBNAIL_SIZE, 260)
    
    def test_header_height(self):
        """Test header height."""
        self.assertEqual(PreviewGenerator.HEADER_HEIGHT, 40)
    
    def test_min_photos_threshold(self):
        """Test minimum photos threshold."""
        self.assertEqual(PreviewGenerator.MIN_PHOTOS_THRESHOLD, 450)
    
    def test_get_image_files(self):
        """Test getting image files from directory."""
        self.create_test_images(10)
        
        gen = PreviewGenerator(self.test_path)
        files = gen.get_image_files()
        
        self.assertEqual(len(files), 10)
        self.assertTrue(all(f.suffix == '.jpg' for f in files))
    
    def test_sampling_less_than_90(self):
        """Test sampling with less than 90 photos."""
        gen = PreviewGenerator(self.test_path)
        num_thumbs, interval = gen.calculate_sampling(50)
        
        self.assertEqual(num_thumbs, 50)
        self.assertEqual(interval, 1)
    
    def test_sampling_between_90_and_450(self):
        """Test sampling with 90-449 photos."""
        gen = PreviewGenerator(self.test_path)
        num_thumbs, interval = gen.calculate_sampling(100)
        
        self.assertEqual(num_thumbs, 90)
        self.assertAlmostEqual(interval, 100 / 90, places=2)
    
    def test_sampling_exactly_450(self):
        """Test sampling with exactly 450 photos."""
        gen = PreviewGenerator(self.test_path)
        num_thumbs, interval = gen.calculate_sampling(450)
        
        self.assertEqual(num_thumbs, 90)
        self.assertEqual(interval, 5)
    
    def test_sampling_more_than_450(self):
        """Test sampling with more than 450 photos."""
        gen = PreviewGenerator(self.test_path)
        num_thumbs, interval = gen.calculate_sampling(500)
        
        self.assertEqual(num_thumbs, 90)
        self.assertEqual(interval, 5)
    
    def test_sample_images_all(self):
        """Test sampling all images when count is less than 90."""
        self.create_test_images(30)
        
        gen = PreviewGenerator(self.test_path)
        files = gen.get_image_files()
        sampled = gen.sample_images(files)
        
        self.assertEqual(len(sampled), 30)
    
    def test_sample_images_fill_slots(self):
        """Test sampling to fill all slots."""
        self.create_test_images(100)
        
        gen = PreviewGenerator(self.test_path)
        files = gen.get_image_files()
        sampled = gen.sample_images(files)
        
        self.assertEqual(len(sampled), 90)
    
    def test_create_thumbnail(self):
        """Test thumbnail creation."""
        self.create_test_images(1)
        
        gen = PreviewGenerator(self.test_path)
        files = gen.get_image_files()
        thumb = gen.create_thumbnail(files[0])
        
        self.assertEqual(thumb.size, (260, 260))
    
    def test_calculate_grid_positions(self):
        """Test grid position calculation."""
        gen = PreviewGenerator(self.test_path)
        positions = gen.calculate_grid_positions()
        
        # Should have 90 positions
        self.assertEqual(len(positions), 90)
        
        # All positions should be tuples of (x, y)
        self.assertTrue(all(isinstance(pos, tuple) and len(pos) == 2 for pos in positions))
        
        # All x coordinates should be within canvas width
        self.assertTrue(all(0 <= x < 3000 for x, y in positions))
        
        # All y coordinates should be at or above header height
        self.assertTrue(all(y >= 40 for x, y in positions))
    
    def test_generate_preview(self):
        """Test preview generation."""
        self.create_test_images(10)
        
        gen = PreviewGenerator(self.test_path)
        output_path = self.test_path / 'test_preview.png'
        result_path = gen.generate_preview(output_path)
        
        # Check that file was created
        self.assertTrue(result_path.exists())
        
        # Check image properties
        with Image.open(result_path) as img:
            self.assertEqual(img.size, (3000, 2000))
            self.assertEqual(img.mode, 'RGBA')
    
    def test_generate_preview_no_images(self):
        """Test that generation fails with no images."""
        gen = PreviewGenerator(self.test_path)
        
        with self.assertRaises(ValueError):
            gen.generate_preview()
    
    def test_invalid_folder(self):
        """Test that invalid folder raises error."""
        with self.assertRaises(ValueError):
            PreviewGenerator('/nonexistent/folder')


if __name__ == '__main__':
    unittest.main()
