#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jinja2",
#   "yt-dlp",
#   "python-slugify",
# ]
# ///

import json
import sys
from pathlib import Path

# Manually set up the test data
video_dir = Path(__file__).parent / "data"
# The actual filenames have &amp; in them, not &
json_file = video_dir / "Kevin Dalton - Karen Bass traveled to Sacramento &amp; asked legislatures for $2 bil....info.json"
video_file = video_dir / "Kevin Dalton - Karen Bass traveled to Sacramento &amp; asked legislatures for $2 bil....mp4"

if not json_file.exists() or not video_file.exists():
    print(f"Test files not found. Please ensure they exist at {json_file} and {video_file}")
    sys.exit(1)

# Load metadata from the existing JSON file
with open(json_file, "r", encoding='utf-8') as f:
    metadata = json.load(f)

# Import the sumvideo script dynamically
import importlib.util

script_path = Path(__file__).parent.parent / "sumvideo.py"
spec = importlib.util.spec_from_file_location("sumvideo", script_path)
sumvideo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sumvideo)

# Create a test HTML file
test_output_dir = Path(__file__).parent / "data/test_output"
test_output_dir.mkdir(exist_ok=True)

html_path = sumvideo.create_html(metadata, str(video_file), str(test_output_dir))
print(f"Test HTML file created at: {html_path}")

# Verify the contents
with open(html_path, "r", encoding='utf-8') as f:
    html_content = f.read()

# Check for double-escaped ampersands
if "&amp;amp;" in html_content:
    print("ERROR: Found double-escaped ampersands in the HTML content!")
    sys.exit(1)
else:
    print("SUCCESS: HTML entities are properly rendered without double escaping.")
    
# Print a snippet of the HTML content around the title
title_index = html_content.find("<title>")
if title_index != -1:
    end_index = html_content.find("</title>", title_index)
    print("\nTitle in HTML:")
    print(html_content[title_index:end_index+8])

print("\nTest completed successfully!")