#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jinja2",
#   "yt-dlp",
#   "python-slugify",
# ]
# ///

import os
import sys
import argparse
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader
from slugify import slugify
import yt_dlp

# HTML template for the description page
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        .video-container {
            width: 100%;
            margin: 20px 0;
        }
        video {
            width: 100%;
            max-height: 600px;
        }
        .metadata {
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .source {
            margin-top: 20px;
            font-style: italic;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .archive-note {
            border-top: 1px solid #ddd;
            margin-top: 30px;
            padding-top: 15px;
            font-size: 0.9em;
            color: #666;
        }
        .download-section {
            margin-top: 20px;
            padding: 15px;
            background-color: #f0f0f0;
            border-radius: 5px;
            display: {{ 'block' if is_standalone else 'none' }};
        }
        .download-button {
            display: inline-block;
            padding: 8px 16px;
            margin-right: 10px;
            background-color: #0066cc;
            color: white;
            border-radius: 4px;
            cursor: pointer;
        }
        .download-button:hover {
            background-color: #0055aa;
        }
    </style>
    {% if is_standalone %}
    <script>
        function downloadFile(dataUrl, filename) {
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        function downloadVideo() {
            const videoDataUrl = document.getElementById('video-player').querySelector('source').src;
            downloadFile(videoDataUrl, "{{ video_filename }}");
        }
        
        function downloadJSON() {
            const jsonData = atob("{{ json_data_base64 }}");
            // Using a properly formatted JSON string
            const blob = new Blob([jsonData], {type: 'application/json'});
            const dataUrl = URL.createObjectURL(blob);
            // Use the same base filename as the HTML file
            downloadFile(dataUrl, "{{ html_filename }}.info.json");
        }
    </script>
    {% endif %}
</head>
<body>
    <h1>{{ title }}</h1>
    
    <div class="video-container">
        <video id="video-player" controls>
            <source src="{{ video_data_url if is_standalone else video_filename }}" type="{{ video_mimetype }}">
            Your browser does not support the video tag.
        </video>
    </div>
    
    <div class="metadata">
        <p><strong>Creator:</strong> {{ uploader }}</p>
        <p><strong>Published:</strong> {{ upload_date }}</p>
        {% if description %}
        <p><strong>Description:</strong></p>
        <p>{{ description }}</p>
        {% endif %}
    </div>
    
    <div class="source">
        <p>Original source: <a href="{{ webpage_url }}" target="_blank">{{ webpage_url }}</a></p>
    </div>
    
    {% if is_standalone %}
    <div class="download-section">
        <p><strong>Download Files:</strong></p>
        <button class="download-button" onclick="downloadVideo()">Download Video</button>
        <button class="download-button" onclick="downloadJSON()">Download JSON Metadata</button>
    </div>
    {% endif %}
    
    <div class="archive-note">
        <p>This is an archived copy of the original content, saved on {{ archive_date }}.</p>
        {% if is_standalone %}
        <p>This is a standalone HTML file with embedded video and JSON data.</p>
        {% endif %}
    </div>
</body>
</html>"""

def format_date(date_str: str) -> str:
    """Format date from YYYYMMDD to ISO format (YYYY-MM-DD)."""
    try:
        date = datetime.strptime(date_str, "%Y%m%d")
        return date.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

def generate_short_slug(title: str, upload_date: Optional[str] = None) -> str:
    """
    Generate a shortened, meaningful slug from a title with optional date suffix.
    
    Args:
        title: Original title to shorten
        upload_date: Optional upload date in YYYYMMDD format for uniqueness
        
    Returns:
        Shortened slug suitable for filenames
    """
    # Truncate title to a reasonable length (max 40 chars)
    short_title = title[:40].strip()
    
    # Remove trailing ellipsis if present
    if short_title.endswith('...'):
        short_title = short_title[:-3].strip()
    
    # Add unique identifier based on upload date if available
    unique_suffix = ''
    if upload_date:
        # Use just the last 4 digits of upload date for uniqueness
        unique_suffix = f"-{upload_date[-4:]}"
    
    # Create and return the slugified result
    return slugify(short_title) + unique_suffix

def get_mime_type(file_extension: str) -> str:
    """Return the MIME type based on file extension."""
    mime_types = {
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'ogg': 'video/ogg',
        'mov': 'video/quicktime',
    }
    return mime_types.get(file_extension.lower(), 'video/mp4')

def download_video(url: str, output_dir: str, format: str = "mp4") -> Optional[Dict[str, Any]]:
    """
    Download a video using yt-dlp and return its metadata.
    
    Args:
        url: URL of the video to download
        output_dir: Directory to save the video
        format: Video format to download
    
    Returns:
        Dictionary containing video metadata or None if download failed
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Set up yt-dlp options
    ydl_opts = {
        'format': f'bestvideo[ext={format}]+bestaudio[ext=m4a]/best[ext={format}]/best',
        'paths': {'home': str(output_path)},
        # Let yt-dlp use its naming pattern for initial download, we'll rename later
        'outtmpl': {'default': '%(title)s.%(ext)s'},
        'writeinfojson': True,
        'writethumbnail': True,
        'keepvideo': True,
    }
    
    try:
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            
            if result is None:
                print(f"Error: Could not extract information from {url}")
                return None
                
            # Return the metadata
            return result
    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading video: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def get_file_as_base64(file_path: str) -> str:
    """
    Convert file content to base64 string.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Base64 encoded string of file content
    """
    with open(file_path, 'rb') as file:
        return base64.b64encode(file.read()).decode('utf-8')

def create_html(metadata: Dict[str, Any], video_path: str, output_dir: str, standalone: bool = False) -> str:
    """
    Create an HTML description page for the video.
    
    Args:
        metadata: Video metadata from yt-dlp
        video_path: Path to the downloaded video file
        output_dir: Directory to save the HTML file
        standalone: Whether to create a standalone HTML file with embedded data
    
    Returns:
        Path to the created HTML file
    """
    # Extract relevant metadata
    title = metadata.get('title', 'Untitled Video')
    uploader = metadata.get('uploader', 'Unknown')
    upload_date = format_date(metadata.get('upload_date', ''))
    description = metadata.get('description', '')
    webpage_url = metadata.get('webpage_url', '')
    
    # Get video filename and MIME type
    video_filename = os.path.basename(video_path)
    
    # Find the actual filename in the output directory as it may have been modified
    # during download (special characters replaced, etc.)
    actual_filename = None
    for file in os.listdir(output_dir):
        if file.endswith(f".{metadata.get('ext', 'mp4')}") and not file.endswith(".info.json"):
            actual_filename = file
            break
    
    if actual_filename:
        video_filename = actual_filename
    
    # URL encode the filename to handle special characters in HTML
    from urllib.parse import quote
    url_safe_filename = quote(video_filename)
    
    file_extension = os.path.splitext(video_filename)[1][1:]  # Remove the dot
    video_mimetype = get_mime_type(file_extension)
    
    # Prepare data for standalone mode
    video_data_url = ""
    json_data_base64 = ""
    
    if standalone:
        # Find and read the video file
        video_file_path = os.path.join(output_dir, video_filename)
        video_base64 = get_file_as_base64(video_file_path)
        video_data_url = f"data:{video_mimetype};base64,{video_base64}"
        
        # Find and read the JSON metadata file
        json_file_path = None
        for file in os.listdir(output_dir):
            if file.endswith(".info.json") and file.startswith(os.path.splitext(video_filename)[0]):
                json_file_path = os.path.join(output_dir, file)
                break
        
        if json_file_path:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                # Load and pretty-print the JSON data with indentation
                json_data = json.loads(f.read())
                formatted_json = json.dumps(json_data, indent=2)
                json_data_base64 = base64.b64encode(formatted_json.encode('utf-8')).decode('utf-8')
    
    # Generate a shorter, meaningful slug for the filename
    slug = generate_short_slug(title, metadata.get('upload_date'))
    html_filename = f"{slug}.html"
    html_path = os.path.join(output_dir, html_filename)
    
    # Create Jinja2 environment and template
    # Disable autoescape to prevent double-escaping of HTML entities
    env = Environment(
        loader=FileSystemLoader(searchpath="./"),
        autoescape=False
    )
    template = env.from_string(HTML_TEMPLATE)
    
    # Render the template with ISO date format for archive date
    archive_date = datetime.now().strftime("%Y-%m-%d")
    
    html_content = template.render(
        title=title,
        uploader=uploader,
        upload_date=upload_date,
        description=description,
        webpage_url=webpage_url,
        video_filename=url_safe_filename,
        video_mimetype=video_mimetype,
        archive_date=archive_date,
        is_standalone=standalone,
        video_data_url=video_data_url,
        json_data_base64=json_data_base64,
        html_filename=slug  # Add html_filename without extension
    )
    
    # Write the HTML file
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_path

def get_default_output_dir() -> str:
    """
    Determine the default output directory for videos.
    
    Checks for XDG_VIDEOS_DIR, then SUMVIDEO_DIR environment variables.
    If neither is set, creates a 'videos' directory in the current working directory.
    
    Returns:
        Path to the default output directory
    """
    # Check for XDG_VIDEOS_DIR
    xdg_videos_dir = os.environ.get('XDG_VIDEOS_DIR')
    if xdg_videos_dir:
        return xdg_videos_dir
    
    # Check for SUMVIDEO_DIR
    sumvideo_dir = os.environ.get('SUMVIDEO_DIR')
    if sumvideo_dir:
        return sumvideo_dir
    
    # Use current working directory with 'videos' subdirectory
    default_dir = Path.cwd() / 'videos'
    default_dir.mkdir(parents=True, exist_ok=True)
    return str(default_dir)

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Download a video and create an HTML description page.')
    parser.add_argument('url', help='URL of the video to download')
    parser.add_argument('-o', '--output-dir', default=None, help='Directory to save the video and HTML files')
    parser.add_argument('-f', '--format', default='mp4', help='Video format to download (mp4, webm, etc.)')
    parser.add_argument('--standalone', action='store_true', help='Create a standalone HTML file with embedded video and metadata')
    args = parser.parse_args()
    
    # Determine output directory
    output_dir = args.output_dir if args.output_dir else get_default_output_dir()
    
    # Download the video
    print(f"Downloading video from {args.url}...")
    metadata = download_video(args.url, output_dir, args.format)
    
    if metadata is None:
        print("Download failed. Exiting.")
        sys.exit(1)
    
    # Get the video title from metadata
    video_title = metadata.get('title', 'video')
    
    # Create a shorter filename using our helper function
    short_slug = generate_short_slug(video_title, metadata.get('upload_date'))
    new_video_filename = f"{short_slug}.{args.format}"
    
    # Define the path for the renamed video file
    new_video_path = os.path.join(output_dir, new_video_filename)
    
    # Find the actual downloaded file (handling any modifications made by yt-dlp)
    actual_video_path = None
    actual_video_filename = None
    
    for file in os.listdir(output_dir):
        # Skip directories and non-video files
        if os.path.isdir(os.path.join(output_dir, file)) or not file.endswith(f".{args.format}"):
            continue
        # Skip .info.json files or any other non-video files
        if file.endswith(".info.json") or "." + args.format not in file:
            continue
        # This is likely our video file
        actual_video_path = os.path.join(output_dir, file)
        actual_video_filename = file
        break
    
    # Rename the video file and its associated files if found
    if actual_video_path and actual_video_filename != new_video_filename:
        # Rename video file
        os.rename(actual_video_path, new_video_path)
        
        # Also rename the .info.json file if it exists
        json_filename = os.path.splitext(actual_video_filename)[0] + ".info.json"
        json_path = os.path.join(output_dir, json_filename)
        if os.path.exists(json_path):
            new_json_path = os.path.join(output_dir, f"{short_slug}.info.json")
            os.rename(json_path, new_json_path)
        
        # And rename the thumbnail if it exists (common extensions)
        for ext in ['.jpg', '.png', '.webp']:
            thumb_filename = os.path.splitext(actual_video_filename)[0] + ext
            thumb_path = os.path.join(output_dir, thumb_filename)
            if os.path.exists(thumb_path):
                new_thumb_path = os.path.join(output_dir, f"{short_slug}{ext}")
                os.rename(thumb_path, new_thumb_path)
                break
        
        # Update the video path for HTML generation
        video_path = new_video_path
    else:
        # Use the original path if we couldn't find the file or rename failed
        video_path = actual_video_path or os.path.join(output_dir, new_video_filename)
    
    # Create the HTML description page
    print("Creating HTML description page...")
    html_path = create_html(metadata, video_path, output_dir, args.standalone)
    
    print("\nDone!")
    print(f"Video saved to: {video_path}")
    print(f"HTML page saved to: {html_path}")
    
    if args.standalone:
        print("Created standalone HTML file with embedded video and metadata.")
        print("You can open the HTML page in your browser to view the video and download the original files.")
    else:
        print("You can open the HTML page in your browser to view the video and its metadata.")

if __name__ == "__main__":
    main()