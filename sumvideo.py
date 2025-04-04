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
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

from jinja2 import Environment, FileSystemLoader
from slugify import slugify
import yt_dlp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('sumvideo')

# Constants
VIDEO_EXTENSIONS = ['mp4', 'webm', 'ogg', 'mov']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
MAX_TITLE_LENGTH = 40
MAX_DESCRIPTION_LENGTH = 150
DEFAULT_VIDEO_FORMAT = 'mp4'

# HTML template for the description page
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    
    <!-- Open Graph metadata for rich previews -->
    <meta property="og:title" content="{{ title }}">
    <meta property="og:type" content="video.other">
    <meta property="og:description" content="{{ short_description }}">
    {% if og_image_data_url %}
    <meta property="og:image" content="{{ og_image_data_url }}">
    {% endif %}
    <meta property="og:site_name" content="SumVideo Archive">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:creator" content="{{ uploader }}">
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
    
   
    <div class="video-container">
        <video id="video-player" controls>
            <source src="{{ video_data_url if is_standalone else video_filename }}" type="{{ video_mimetype }}">
            Your browser does not support the video tag.
        </video>
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
    if not title:
        title = "untitled"
        
    # Truncate title to a reasonable length
    short_title = title[:MAX_TITLE_LENGTH].strip()
    
    # Remove trailing ellipsis if present
    if short_title.endswith('...'):
        short_title = short_title[:-3].strip()
    
    # Add unique identifier based on upload date if available
    unique_suffix = ''
    if upload_date and len(upload_date) >= 4:
        # Use just the last 4 digits of upload date for uniqueness
        unique_suffix = f"-{upload_date[-4:]}"
    
    # Create and return the slugified result
    return slugify(short_title) + unique_suffix

def get_mime_type(file_extension: str) -> str:
    """
    Return the MIME type based on file extension.
    
    Args:
        file_extension: The extension of the file (without dot)
        
    Returns:
        MIME type string for the video format
    """
    mime_types = {
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'ogg': 'video/ogg',
        'mov': 'video/quicktime',
    }
    return mime_types.get(file_extension.lower(), 'video/mp4')

def download_video(url: str, output_dir: Union[str, Path], format: str = DEFAULT_VIDEO_FORMAT) -> Optional[Dict[str, Any]]:
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
        logger.info(f"Downloading video from {url} to {output_path}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            
            if result is None:
                logger.error(f"Could not extract information from {url}")
                return None
                
            logger.info(f"Successfully downloaded video: {result.get('title', 'Unknown')}")
            return result
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error downloading video: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return None

def get_file_as_base64(file_path: Union[str, Path]) -> str:
    """
    Convert file content to base64 string.
    
    Args:
        file_path: Path to the file (string or Path object)
        
    Returns:
        Base64 encoded string of file content
        
    Raises:
        IOError: If file cannot be read
    """
    path_obj = Path(file_path) if isinstance(file_path, str) else file_path
    
    try:
        with path_obj.open('rb') as file:
            return base64.b64encode(file.read()).decode('utf-8')
    except (IOError, OSError) as e:
        logger.error(f"Failed to read file for base64 encoding: {path_obj} - {e}")
        raise

def get_image_mime_type(file_path: Union[str, Path]) -> str:
    """
    Determine the MIME type of an image based on its extension.
    
    Args:
        file_path: Path to the image file (string or Path object)
        
    Returns:
        MIME type string for the image
    """
    path_obj = Path(file_path) if isinstance(file_path, str) else file_path
    ext = path_obj.suffix.lower()
    
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
    }
    return mime_types.get(ext, 'image/jpeg')  # Default to JPEG if unknown

def create_html(metadata: Dict[str, Any], video_path: Union[str, Path], output_dir: Union[str, Path], 
              standalone: bool = False) -> str:
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
    # Convert paths to Path objects
    video_path_obj = Path(video_path) if isinstance(video_path, str) else video_path
    output_dir_obj = Path(output_dir) if isinstance(output_dir, str) else output_dir
    
    # Extract relevant metadata
    title = metadata.get('title', 'Untitled Video')
    uploader = metadata.get('uploader', 'Unknown')
    upload_date = format_date(metadata.get('upload_date', ''))
    description = metadata.get('description', '')
    webpage_url = metadata.get('webpage_url', '')
    
    # Create a shortened description for OG metadata
    short_description = description
    if description and len(description) > MAX_DESCRIPTION_LENGTH:
        short_description = description[:MAX_DESCRIPTION_LENGTH] + '...'
    
    # Get video filename and MIME type
    video_filename = video_path_obj.name
    
    # URL encode the filename to handle special characters in HTML
    from urllib.parse import quote
    url_safe_filename = quote(video_filename)
    
    # Get the file extension and MIME type
    file_extension = video_path_obj.suffix[1:]  # Remove the dot
    video_mimetype = get_mime_type(file_extension)
    
    # Prepare data for standalone mode and rich previews
    video_data_url = ""
    json_data_base64 = ""
    og_image_data_url = ""
    
    # Get the base filename for associated files (without extension)
    base_filename = video_path_obj.stem
    
    # Get thumbnail path directly from metadata if available
    thumbnail_path = None
    if 'thumbnail' in metadata and metadata['thumbnail']:
        thumbnail_str = str(metadata['thumbnail'])
        potential_thumbnail = Path(thumbnail_str)
        if potential_thumbnail.exists():
            thumbnail_path = potential_thumbnail
        else:
            # Try to find the thumbnail in the output directory with the same filename
            potential_thumbnail = output_dir_obj / Path(thumbnail_str).name
            if potential_thumbnail.exists():
                thumbnail_path = potential_thumbnail
    
    # If no thumbnail path from metadata, try to derive it from yt-dlp naming pattern
    if not thumbnail_path:
        # yt-dlp typically names the thumbnail with the same base name as the video
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            potential_path = output_dir_obj / f"{base_filename}{ext}"
            if potential_path.exists():
                thumbnail_path = potential_path
                break
    
    # If thumbnail found, create data URL for OG image
    if thumbnail_path:
        try:
            thumbnail_mime = get_image_mime_type(thumbnail_path)
            thumbnail_base64 = get_file_as_base64(thumbnail_path)
            og_image_data_url = f"data:{thumbnail_mime};base64,{thumbnail_base64}"
        except Exception as e:
            logger.error(f"Error creating thumbnail data URL: {e}")
    
    if standalone:
        try:
            # Use the exact video path provided rather than searching
            if video_path_obj.exists():
                video_base64 = get_file_as_base64(video_path_obj)
                video_data_url = f"data:{video_mimetype};base64,{video_base64}"
            else:
                logger.warning(f"Video file not found for standalone mode: {video_path_obj}")
            
            # Get JSON path derived from metadata
            json_file_path = output_dir_obj / f"{base_filename}.info.json"
            
            if json_file_path.exists():
                try:
                    # Load and pretty-print the JSON data with indentation
                    json_content = json_file_path.read_text(encoding='utf-8')
                    json_data = json.loads(json_content)
                    formatted_json = json.dumps(json_data, indent=2)
                    json_data_base64 = base64.b64encode(formatted_json.encode('utf-8')).decode('utf-8')
                except Exception as e:
                    logger.error(f"Error processing JSON file: {e}")
        except Exception as e:
            logger.error(f"Error preparing standalone data: {e}", exc_info=True)
    
    # Generate a shorter, meaningful slug for the filename
    slug = generate_short_slug(title, metadata.get('upload_date'))
    html_filename = f"{slug}.html"
    html_path = output_dir_obj / html_filename
    
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
        short_description=short_description,
        webpage_url=webpage_url,
        video_filename=url_safe_filename,
        video_mimetype=video_mimetype,
        archive_date=archive_date,
        is_standalone=standalone,
        video_data_url=video_data_url,
        json_data_base64=json_data_base64,
        html_filename=slug,  # HTML filename without extension
        og_image_data_url=og_image_data_url  # Thumbnail for rich previews
    )
    
    # Write the HTML file
    try:
        html_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Created HTML file: {html_path}")
    except Exception as e:
        logger.error(f"Error writing HTML file: {e}")
    
    return str(html_path)

# This function has been removed as we now directly derive filenames from yt-dlp output
# rather than searching for files by extension

def get_default_output_dir() -> Path:
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
        result = Path(xdg_videos_dir)
        result.mkdir(parents=True, exist_ok=True)
        return result
    
    # Check for SUMVIDEO_DIR
    sumvideo_dir = os.environ.get('SUMVIDEO_DIR')
    if sumvideo_dir:
        result = Path(sumvideo_dir)
        result.mkdir(parents=True, exist_ok=True)
        return result
    
    # Use current working directory with 'videos' subdirectory
    default_dir = Path.cwd() / 'videos'
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Download a video and create an HTML description page.',
        epilog='''
Examples:
  sumvideo.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
  sumvideo.py --standalone https://twitter.com/username/status/123456789
  sumvideo.py -o ~/Videos -f webm https://vimeo.com/123456789
        '''
    )
    parser.add_argument('url', help='URL of the video to download')
    parser.add_argument('-o', '--output-dir', default=None, 
                      help='Directory to save the video and HTML files')
    parser.add_argument('-f', '--format', default=DEFAULT_VIDEO_FORMAT, 
                      help=f'Video format to download ({", ".join(VIDEO_EXTENSIONS)})')
    parser.add_argument('--standalone', action='store_true', 
                      help='Create a standalone HTML file with embedded video and metadata')
    parser.add_argument('--keep-all', action='store_true', 
                      help='Keep all downloaded files (default is to clean up)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                      help='Enable verbose logging')
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else get_default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download the video
    logger.info(f"Downloading video from {args.url}...")
    metadata = download_video(args.url, output_dir, args.format)
    
    if metadata is None:
        logger.error("Download failed. Exiting.")
        sys.exit(1)
    
    # Get the video title from metadata
    video_title = metadata.get('title', 'video')
    
    # Create a shorter filename using our helper function
    short_slug = generate_short_slug(video_title, metadata.get('upload_date'))
    new_video_filename = f"{short_slug}.{args.format}"
    
    # Define the path for the renamed video file
    new_video_path = output_dir / new_video_filename
    
    # Find the actual downloaded file using glob instead of manual search
    video_files = list(output_dir.glob(f"*.{args.format}"))
    
    # Filter out any .info.json files that might be incorrectly matched
    video_files = [f for f in video_files if not f.name.endswith(".info.json")]
    
    # Find the actual video file
    actual_video_path = None
    
    if video_files:
        actual_video_path = video_files[0]
    
    # Get the actual downloaded file path from the metadata
    video_path = None
    if 'requested_downloads' in metadata and metadata['requested_downloads']:
        # yt-dlp stores the actual downloaded filepath in the requested_downloads
        for download in metadata['requested_downloads']:
            if 'filepath' in download and Path(download['filepath']).exists():
                actual_video_path = Path(download['filepath'])
                logger.debug(f"Found video path from metadata: {actual_video_path}")
                video_path = actual_video_path
                break
    
    # Fallback to searching if not found in metadata
    if not video_path:
        # Find the downloaded file in the output directory
        video_ext = metadata.get('ext', args.format)
        video_files = list(output_dir.glob(f"*.{video_ext}"))
        # Filter out any .info.json files that might be incorrectly matched
        video_files = [f for f in video_files if not f.name.endswith(".info.json")]
        
        if video_files:
            actual_video_path = video_files[0]
            video_path = actual_video_path
        else:
            # Last resort: use the expected filename
            video_path = output_dir / f"{metadata.get('title', 'video')}.{args.format}"
    
    # Rename files to use the slug if they're not already using it
    if video_path and video_path.name != new_video_filename:
        try:
            logger.debug(f"Renaming video file from {video_path} to {new_video_path}")
            
            # Get the base filename without extension before renaming
            original_base = video_path.stem
            
            # Rename video file
            video_path.rename(new_video_path)
            
            # Find and rename the JSON metadata file
            json_path = output_dir / f"{original_base}.info.json"
            if json_path.exists():
                new_json_path = output_dir / f"{short_slug}.info.json"
                logger.debug(f"Renaming JSON file from {json_path} to {new_json_path}")
                json_path.rename(new_json_path)
            
            # Find and rename thumbnail file based on yt-dlp's naming convention
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                thumb_path = output_dir / f"{original_base}{ext}"
                if thumb_path.exists():
                    new_thumb_path = output_dir / f"{short_slug}{ext}"
                    logger.debug(f"Renaming thumbnail from {thumb_path} to {new_thumb_path}")
                    thumb_path.rename(new_thumb_path)
            
            # Update the video path for HTML generation
            video_path = new_video_path
            
        except OSError as e:
            logger.error(f"Error renaming files: {e}")
            # If renaming failed, the original path is now invalid, so use the new path
            video_path = new_video_path if new_video_path.exists() else video_path
    
    # Create the HTML description page
    logger.info("Creating HTML description page...")
    html_path = create_html(metadata, str(video_path), str(output_dir), args.standalone)
    html_path = Path(html_path)  # Convert back to Path object
    
    # Determine if we should clean up files (default is yes, unless --keep-all is specified)
    should_cleanup = not args.keep_all
    if should_cleanup:
        files_to_remove = []
        
        # In standalone mode, we can remove the video file because it's embedded in HTML
        if args.standalone and new_video_path.exists():
            files_to_remove.append(new_video_path)
        
        # JSON metadata file using the slugified name
        json_path = output_dir / f"{short_slug}.info.json"
        if json_path.exists():
            files_to_remove.append(json_path)
        
        # Thumbnail file based on yt-dlp's naming convention
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            thumb_path = output_dir / f"{short_slug}{ext}"
            if thumb_path.exists():
                files_to_remove.append(thumb_path)
                
        # Also check for uppercase extensions that might be used by yt-dlp
        for ext in ['.JPG', '.JPEG', '.PNG', '.WEBP']:
            thumb_path = output_dir / f"{short_slug}{ext}"
            if thumb_path.exists():
                files_to_remove.append(thumb_path)
        
        # Handle thumbnail files that might be stored with the full video id
        if 'id' in metadata:
            video_id = metadata['id']
            for ext in ['.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP']:
                thumb_path = output_dir / f"{video_id}{ext}"
                if thumb_path.exists():
                    files_to_remove.append(thumb_path)
                    
        # Filter out the HTML file we just created and remove duplicates
        files_to_remove = [f for f in files_to_remove if f != html_path]
        files_to_remove = list(set(files_to_remove))  # Remove duplicates
        
        # Remove the files
        if files_to_remove:
            logger.info("Cleaning up downloaded files...")
            for file_path in files_to_remove:
                try:
                    file_path.unlink()
                    logger.info(f"Removed: {file_path.name}")
                except OSError as e:
                    logger.error(f"Failed to remove {file_path.name}: {e}")
    
    logger.info("Done!")
    if not (should_cleanup and args.standalone):
        logger.info(f"Video saved to: {video_path}")
    logger.info(f"HTML page saved to: {html_path}")
    
    # Print final status for user
    print(f"\nSuccessfully downloaded and processed: {video_title}")
    print(f"HTML page created: {html_path}")
    
    if args.standalone:
        print("Created standalone HTML file with embedded video and metadata.")
        if should_cleanup:
            print("Original files have been removed automatically.")
            print("You can extract the video and JSON from the HTML page using the download buttons.")
        else:
            print("Original files kept (--keep-all).")
            print("You can open the HTML page in your browser to view the video and download the original files.")
    else:
        if should_cleanup:
            print("JSON and thumbnail files have been removed automatically, but video file is preserved.")
            print("Use --keep-all to keep all downloaded files.")
        else:
            print("All original files kept (--keep-all).")
        print("You can open the HTML page in your browser to view the video and its metadata.")

if __name__ == "__main__":
    main()
