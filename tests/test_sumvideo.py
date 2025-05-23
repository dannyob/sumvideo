#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jinja2",
#   "yt-dlp",
#   "python-slugify",
#   "pytest",
# ]
# ///

import os
import unittest
import importlib.util
from pathlib import Path
import tempfile
import base64
import json
import re


class TestSumVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Dynamically load the sumvideo module after dependencies are installed."""
        # Get the absolute path to the sumvideo.py file
        script_dir = Path(__file__).parent.parent.absolute()
        module_path = script_dir / "sumvideo.py"
        
        # Load the module dynamically
        spec = importlib.util.spec_from_file_location("sumvideo", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Store module functions as class attributes for testing
        cls.create_html = module.create_html
        cls.format_date = module.format_date
        cls.get_mime_type = module.get_mime_type
        cls.get_file_as_base64 = module.get_file_as_base64
        cls.HTML_TEMPLATE = module.HTML_TEMPLATE

    def setUp(self):
        # Create a temporary directory for test outputs
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = self.temp_dir.name
        
        # Sample metadata with HTML entities
        self.sample_metadata = {
            'title': 'Test Video with &amp; symbol',
            'uploader': 'Test Uploader',
            'upload_date': '20250328',
            'description': 'This is a description with &amp; and other &lt;special&gt; characters',
            'webpage_url': 'https://example.com/video?param1=value1&amp;param2=value2',
        }
        
        # Sample video path
        self.video_path = os.path.join(self.output_dir, 'Test Video with &amp; symbol.mp4')
        
        # Create an empty file at the video path
        Path(self.video_path).touch()

    def tearDown(self):
        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def test_html_entity_rendering(self):
        """Test that HTML entities are rendered correctly in the HTML output."""
        # Create the HTML file
        html_path = TestSumVideo.create_html(self.sample_metadata, self.video_path, self.output_dir)
        
        # Read the HTML content
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Check that the HTML entities are not double-escaped
        self.assertIn('Test Video with &amp; symbol', html_content)
        self.assertNotIn('Test Video with &amp;amp; symbol', html_content)
        
        # Check that the description is rendered correctly
        self.assertIn('This is a description with &amp; and other &lt;special&gt; characters', html_content)
        self.assertNotIn('&amp;amp;', html_content)
        
        # Check that the URL is rendered correctly
        self.assertIn('https://example.com/video?param1=value1&amp;param2=value2', html_content)
        self.assertNotIn('&amp;amp;', html_content)

    def test_format_date(self):
        """Test that dates are formatted correctly."""
        # Test valid date format
        self.assertEqual(TestSumVideo.format_date('20250328'), '2025-03-28')
        
        # Test invalid date format
        self.assertEqual(TestSumVideo.format_date('invalid'), 'invalid')

    def test_get_mime_type(self):
        """Test that MIME types are returned correctly."""
        self.assertEqual(TestSumVideo.get_mime_type('mp4'), 'video/mp4')
        self.assertEqual(TestSumVideo.get_mime_type('webm'), 'video/webm')
        self.assertEqual(TestSumVideo.get_mime_type('unknown'), 'video/mp4')  # Default
        
    def test_standalone_mode(self):
        """Test that standalone mode embeds video and JSON data correctly."""
        # Create a JSON metadata file
        json_path = os.path.join(self.output_dir, 'Test Video with &amp; symbol.info.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.sample_metadata, f)
            
        # Write some content to the video file
        with open(self.video_path, 'wb') as f:
            f.write(b'test video content')
            
        # Create HTML with standalone mode
        html_path = TestSumVideo.create_html(self.sample_metadata, self.video_path, self.output_dir, standalone=True)
        
        # Read the HTML content
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Check that video data is embedded
        self.assertIn('data:video/mp4;base64,', html_content)
        
        # Check that JSON data is embedded
        json_match = re.search(r'atob\("([^"]+)"\)', html_content)
        self.assertIsNotNone(json_match, "JSON base64 data not found in HTML")
        
        # Decode and verify JSON content
        if json_match:
            base64_data = json_match.group(1)
            try:
                decoded_json = base64.b64decode(base64_data).decode('utf-8')
                json_data = json.loads(decoded_json)
                self.assertEqual(json_data['title'], self.sample_metadata['title'])
            except:
                self.fail("Failed to decode embedded JSON data")
        
        # Check for download buttons
        self.assertIn('downloadVideo()', html_content)
        self.assertIn('downloadJSON()', html_content)
        self.assertIn('class="download-button"', html_content)


if __name__ == '__main__':
    unittest.main()