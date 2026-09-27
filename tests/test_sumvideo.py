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

import base64
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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
        cls.STYLES = module.STYLES
        cls.module = module

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
            except ValueError:
                self.fail("Failed to decode embedded JSON data")
            self.assertEqual(json_data['title'], self.sample_metadata['title'])
        
        # Check for download buttons
        self.assertIn('downloadVideo()', html_content)
        self.assertIn('downloadJSON()', html_content)
        self.assertIn('class="download-button"', html_content)

    def _render(self, **kwargs):
        html_path = TestSumVideo.create_html(
            self.sample_metadata, self.video_path, self.output_dir, **kwargs)
        return Path(html_path).read_text(encoding='utf-8')

    THUMB_URL_NAME = 'Test%20Video%20with%20%26amp%3B%20symbol.jpg'

    def _write_thumbnail(self):
        thumb = Path(self.output_dir) / 'Test Video with &amp; symbol.jpg'
        thumb.write_bytes(b'\xff\xd8\xff fake jpeg')
        return thumb

    def test_thumbnail_file_used_as_poster_and_og_image(self):
        """Normal pages reference the thumbnail file instead of embedding it."""
        self._write_thumbnail()
        html_content = self._render()
        self.assertIn(f'poster="{self.THUMB_URL_NAME}"', html_content)
        self.assertIn(f'<meta property="og:image" content="{self.THUMB_URL_NAME}">',
                      html_content)
        self.assertNotIn('data:image', html_content)
        self.assertNotIn('og:url', html_content)

    def test_base_url_makes_absolute_og_urls(self):
        """With a base URL, og:image and og:url are absolute."""
        self._write_thumbnail()
        html_content = self._render(base_url='https://example.com/videos')
        self.assertIn('<meta property="og:image" content='
                      f'"https://example.com/videos/{self.THUMB_URL_NAME}">', html_content)
        self.assertRegex(html_content, r'<meta property="og:url" '
                         r'content="https://example\.com/videos/test-video-[a-z0-9-]+\.html">')
        # The poster stays relative so the page also works when opened locally
        self.assertIn(f'poster="{self.THUMB_URL_NAME}"', html_content)

    def test_standalone_embeds_poster_once_and_skips_og_image(self):
        """Standalone pages embed the thumbnail as the poster and have no og:image."""
        self._write_thumbnail()
        html_content = self._render(standalone=True)
        self.assertRegex(html_content, r'<video[^>]*poster="data:image/jpeg;base64,')
        self.assertEqual(html_content.count('data:image/jpeg;base64,'), 1)
        self.assertNotIn('og:image', html_content)

    def test_public_url(self):
        """Public URLs join the base URL and a quoted filename."""
        public_url = TestSumVideo.module.public_url
        self.assertEqual(public_url('https://example.com/v', 'a b.html'),
                         'https://example.com/v/a%20b.html')
        self.assertEqual(public_url('https://example.com/v/', 'a.html'),
                         'https://example.com/v/a.html')

    def test_base_url_only_applies_to_default_output_dir(self):
        """SUMVIDEO_BASE_URL describes the default directory, not arbitrary -o paths."""
        get_base_url = TestSumVideo.module.get_base_url
        env = {'SUMVIDEO_DIR': self.output_dir, 'SUMVIDEO_BASE_URL': 'https://example.com/v'}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(get_base_url(Path(self.output_dir)), 'https://example.com/v')
            self.assertIsNone(get_base_url(Path(self.output_dir) / 'elsewhere'))
        with mock.patch.dict(os.environ, {'SUMVIDEO_DIR': self.output_dir}, clear=True):
            self.assertIsNone(get_base_url(Path(self.output_dir)))

    @unittest.skipUnless(shutil.which('ffmpeg'), 'needs ffmpeg')
    def test_non_jpeg_thumbnail_converted_to_jpeg(self):
        """webp/png thumbnails are converted to jpg, which link previews handle better."""
        png = Path(self.output_dir) / 'thumb.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=16x16',
                        '-frames:v', '1', str(png)], check=True)
        result = TestSumVideo.module.ensure_jpeg_thumbnail(png)
        self.assertEqual(result, png.with_suffix('.jpg'))
        self.assertTrue(result.read_bytes().startswith(b'\xff\xd8'))
        self.assertFalse(png.exists())

    def test_thumbnail_files_uses_real_filenames(self):
        """Only real directory entries are returned, whatever the filesystem's case rules."""
        thumbnail_files = TestSumVideo.module.thumbnail_files
        (Path(self.output_dir) / 'clip.jpg').write_bytes(b'x')
        (Path(self.output_dir) / 'other.JPG').write_bytes(b'x')
        (Path(self.output_dir) / 'clip.mp4').write_bytes(b'x')
        self.assertEqual([p.name for p in thumbnail_files(Path(self.output_dir), 'clip')],
                         ['clip.jpg'])
        self.assertEqual([p.name for p in thumbnail_files(Path(self.output_dir), 'other')],
                         ['other.JPG'])

    def test_jpeg_thumbnail_left_alone(self):
        thumb = self._write_thumbnail()
        self.assertEqual(TestSumVideo.module.ensure_jpeg_thumbnail(thumb), thumb)

    def test_no_poster_without_thumbnail(self):
        """No poster attribute when there is no thumbnail."""
        self.assertNotIn('poster=', self._render())

    def test_description_keeps_line_breaks_in_every_style(self):
        """Descriptions are plain text; their newlines must survive in all styles."""
        self.sample_metadata['description'] = 'First line\nSecond line'
        for style in TestSumVideo.STYLES:
            with self.subTest(style=style):
                html_content = self._render(style=style)
                self.assertIn('<p class="description">First line\nSecond line</p>',
                              html_content)
                self.assertRegex(html_content,
                                 r'\.description\s*\{[^}]*white-space:\s*pre-line')

    def test_default_style_supports_dark_mode(self):
        """The default style should follow the system dark mode setting."""
        self.assertIn('prefers-color-scheme: dark', self._render(style='default'))

    def _ydl_opts_used(self, **kwargs):
        """Run download_video with yt-dlp mocked out; return the options it was given."""
        with mock.patch.object(TestSumVideo.module.yt_dlp, 'YoutubeDL') as ydl:
            ydl.return_value.__enter__.return_value.extract_info.return_value = {'title': 't'}
            TestSumVideo.module.download_video('https://example.com/v', self.output_dir,
                                               **kwargs)
        return ydl.call_args.args[0]

    def test_download_removes_intermediate_streams_by_default(self):
        """Separate video/audio streams should be deleted after yt-dlp merges them."""
        self.assertFalse(self._ydl_opts_used().get('keepvideo', False))

    def test_download_keeps_intermediate_streams_with_keep_all(self):
        """--keep-all keeps everything, including the separate streams."""
        self.assertTrue(self._ydl_opts_used(keep_all=True).get('keepvideo'))


    def _make_page(self, stem, title, upload_date, thumbnail=True, standalone=False):
        """Create a sumvideo page (and its video/thumbnail files) in the output dir."""
        video = Path(self.output_dir) / f'{stem}.mp4'
        video.write_bytes(b'video')
        if thumbnail:
            (Path(self.output_dir) / f'{stem}.jpg').write_bytes(b'\xff\xd8\xff jpeg')
        meta = dict(self.sample_metadata, title=title, upload_date=upload_date)
        return Path(TestSumVideo.create_html(meta, video, self.output_dir,
                                             standalone=standalone))

    def test_read_page_info(self):
        """Title, creator, date and thumbnail are read back from a generated page."""
        self._write_thumbnail()
        page = Path(TestSumVideo.create_html(self.sample_metadata, self.video_path,
                                             self.output_dir))
        info = TestSumVideo.module.read_page_info(page)
        self.assertEqual(info['title'], 'Test Video with & symbol')
        self.assertEqual(info['creator'], 'Test Uploader')
        self.assertEqual(info['published'], '2025-03-28')
        self.assertEqual(info['thumbnail'], 'Test Video with &amp; symbol.jpg')
        self.assertEqual(info['filename'], page.name)

    def test_read_page_info_reads_pages_from_before_open_graph(self):
        """Early pages have no og: tags but do have sumvideo's archive note."""
        old = Path(self.output_dir) / 'old.html'
        old.write_text('<html><head><title>Old one</title></head><body>'
                       '<h1>Old one</h1><div class="metadata">'
                       '<p><strong>Creator:</strong> Someone</p>'
                       '<p><strong>Published:</strong> 2025-03-30</p></div>'
                       '<div class="archive-note"><p>This is an archived copy of the '
                       'original content, saved on 2025-03-30.</p></div></body></html>')
        info = TestSumVideo.module.read_page_info(old)
        self.assertEqual((info['title'], info['creator'], info['published']),
                         ('Old one', 'Someone', '2025-03-30'))

    def test_read_page_info_ignores_other_html(self):
        other = Path(self.output_dir) / 'other.html'
        other.write_text('<html><head><title>Not ours</title></head></html>')
        self.assertIsNone(TestSumVideo.module.read_page_info(other))

    def test_build_index_lists_pages_newest_first(self):
        """The index links every sumvideo page, newest first, and nothing else."""
        older = self._make_page('older', 'Older &amp; wiser', '20240101')
        newer = self._make_page('newer', 'Newer video', '20250601')
        (Path(self.output_dir) / 'other.html').write_text('<html></html>')
        index = TestSumVideo.module.build_index(Path(self.output_dir))
        self.assertEqual(index, Path(self.output_dir) / 'index.html')
        html_content = index.read_text(encoding='utf-8')
        self.assertIn(f'href="{newer.name}"', html_content)
        self.assertIn(f'href="{older.name}"', html_content)
        self.assertLess(html_content.index(newer.name), html_content.index(older.name))
        self.assertNotIn('other.html', html_content)
        self.assertIn('Older &amp; wiser', html_content)
        self.assertNotIn('&amp;amp;', html_content)
        self.assertIn('src="older.jpg"', html_content)
        # Rebuilding must not list the index itself
        html_again = TestSumVideo.module.build_index(Path(self.output_dir)).read_text()
        self.assertNotIn('href="index.html"', html_again)

    def test_build_index_leaves_out_embedded_images(self):
        """Standalone pages' embedded posters are too big to copy into the index."""
        self._make_page('solo', 'Standalone', '20250101', standalone=True)
        html_content = TestSumVideo.module.build_index(Path(self.output_dir)).read_text()
        self.assertIn('Standalone', html_content)
        self.assertNotIn('data:', html_content)

    def test_build_index_with_base_url(self):
        self._make_page('clip', 'Clip', '20250101')
        index = TestSumVideo.module.build_index(Path(self.output_dir),
                                                base_url='https://example.com/v/')
        self.assertIn('<meta property="og:url" content="https://example.com/v/index.html">',
                      index.read_text())

    def test_index_option_needs_no_url(self):
        """`sumvideo --index` rebuilds the index without downloading anything."""
        self._make_page('clip', 'Clip', '20250101')
        argv = ['sumvideo', '--index', '-o', self.output_dir]
        with mock.patch.object(TestSumVideo.module.sys, 'argv', argv), \
             mock.patch.object(TestSumVideo.module, 'download_video') as download:
            TestSumVideo.module.main()
        download.assert_not_called()
        self.assertIn('clip', (Path(self.output_dir) / 'index.html').read_text())

    def test_url_required_without_index(self):
        with mock.patch.object(TestSumVideo.module.sys, 'argv', ['sumvideo']), \
             mock.patch('sys.stderr'), self.assertRaises(SystemExit):
            TestSumVideo.module.main()


    def test_tags_written_as_video_tag_meta(self):
        """Each tag becomes its own og video:tag line, escaped, easy to edit by hand."""
        html_content = self._render(tags=['cats', 'Rock & Roll'])
        self.assertIn('<meta property="video:tag" content="cats">', html_content)
        self.assertIn('<meta property="video:tag" content="Rock &amp; Roll">', html_content)
        self.assertNotIn('video:tag', self._render())

    def test_read_page_info_returns_tags(self):
        page = self._make_page('tagged', 'Tagged', '20250101')
        text = page.read_text().replace(
            '<meta property="og:site_name"',
            '<meta property="video:tag" content="cats">\n'
            '    <meta property="video:tag" content="Rock &amp; Roll">\n'
            '    <meta property="og:site_name"', 1)
        page.write_text(text)
        info = TestSumVideo.module.read_page_info(page)
        self.assertEqual(info['tags'], ['cats', 'Rock & Roll'])
        plain = self._make_page('plain', 'Plain', '20250101')
        self.assertEqual(TestSumVideo.module.read_page_info(plain)['tags'], [])

    def test_index_filters_by_tag_without_javascript(self):
        """Tag links target anchors before the list; CSS hides non-matching entries."""
        for stem, tags in [('a', ['cats']), ('b', ['cats', 'Rock & Roll']), ('c', [])]:
            video = Path(self.output_dir) / f'{stem}.mp4'
            video.write_bytes(b'v')
            meta = dict(self.sample_metadata, title=f'Video {stem}', upload_date='20250101')
            TestSumVideo.create_html(meta, video, self.output_dir, tags=tags)
        html_content = TestSumVideo.module.build_index(Path(self.output_dir)).read_text()
        self.assertNotIn('<script', html_content)
        self.assertIn('href="#tag-cats">cats</a> <span class="count">2</span>', html_content)
        self.assertIn('href="#tag-rock-roll">Rock &amp; Roll</a> <span class="count">1</span>',
                      html_content)
        self.assertIn('#tag-cats:target ~ ol > li:not(.t-cats)', html_content)
        self.assertIn('#tag-rock-roll:target ~ ol > li:not(.t-rock-roll)', html_content)
        self.assertLess(html_content.index('id="tag-cats"'), html_content.index('<ol>'))
        self.assertIn('<li class="t-cats t-rock-roll">', html_content)
        self.assertIn('<li class="t-cats">', html_content)
        self.assertIn('<li class="">', html_content)
        self.assertEqual(html_content.count('<script'), 0)

    def test_index_without_tags_has_no_tag_nav(self):
        self._make_page('clip', 'Clip', '20250101')
        html_content = TestSumVideo.module.build_index(Path(self.output_dir)).read_text()
        self.assertNotIn('class="tags"', html_content)

    def test_tag_option(self):
        """`sumvideo --tag a --tag b URL` writes both tags into the page."""
        out = Path(self.output_dir)

        def fake_download(url, output_dir, *args, **kwargs):
            video = Path(output_dir) / 'Downloaded.mp4'
            video.write_bytes(b'video')
            return {'title': 'Downloaded', 'upload_date': '20250101', 'uploader': 'U',
                    'webpage_url': url, 'requested_downloads': [{'filepath': str(video)}]}

        argv = ['sumvideo', '--tag', 'cats', '--tag', 'music', '-o', str(out),
                'https://example.com/v']
        with mock.patch.object(TestSumVideo.module.sys, 'argv', argv), \
             mock.patch.object(TestSumVideo.module, 'download_video', fake_download), \
             mock.patch('builtins.print'):
            TestSumVideo.module.main()
        page = next(p for p in out.glob('*.html') if p.name != 'index.html')
        self.assertEqual(TestSumVideo.module.read_page_info(page)['tags'], ['cats', 'music'])


if __name__ == '__main__':
    unittest.main()