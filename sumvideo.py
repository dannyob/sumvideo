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
from typing import Dict, Any, Optional, List, Union

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
    
    # Find the actual filename in the output directory if needed
    video_ext = metadata.get('ext', DEFAULT_VIDEO_FORMAT)
    video_files = list(output_dir_obj.glob(f"*.{video_ext}"))
    video_files = [f for f in video_files if not f.name.endswith(".info.json")]
    
    if video_files and video_path_obj.name != video_files[0].name:
        video_filename = video_files[0].name
    
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
    
    # Find thumbnail image for OG metadata using our helper function
    base_filename = video_path_obj.stem
    image_exts = [ext[1:] if ext.startswith('.') else ext for ext in IMAGE_EXTENSIONS]
    thumbnail_files = find_files_by_extension(output_dir_obj, base_filename, image_exts)
    
    # If thumbnail found, create data URL for OG image
    if thumbnail_files:
        thumbnail_path = thumbnail_files[0]
        try:
            thumbnail_mime = get_image_mime_type(thumbnail_path)
            thumbnail_base64 = get_file_as_base64(thumbnail_path)
            og_image_data_url = f"data:{thumbnail_mime};base64,{thumbnail_base64}"
        except Exception as e:
            logger.error(f"Error creating thumbnail data URL: {e}")
    
    if standalone:
        try:
            # Find and read the video file
            video_file_path = output_dir_obj / video_filename
            if video_file_path.exists():
                video_base64 = get_file_as_base64(video_file_path)
                video_data_url = f"data:{video_mimetype};base64,{video_base64}"
            else:
                logger.warning(f"Video file not found for standalone mode: {video_file_path}")
            
            # Find and read the JSON metadata file
            json_files = list(output_dir_obj.glob(f"{base_filename}.info.json"))
            
            if json_files:
                json_file_path = json_files[0]
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

def find_files_by_extension(directory: Union[str, Path], base_name: str, extensions: List[str]) -> List[Path]:
    """
    Find files with a specific base name and extensions in a directory.
    
    Args:
        directory: Directory to search in
        base_name: Base name of the files to find
        extensions: List of extensions to search for (with or without dot)
        
    Returns:
        List of Path objects for the found files
    """
    dir_path = Path(directory) if isinstance(directory, str) else directory
    found_files = []
    
    # Normalize extensions to include the dot
    normalized_exts = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
    
    try:
        for ext in normalized_exts:
            potential_file = dir_path / f"{base_name}{ext}"
            if potential_file.exists():
                found_files.append(potential_file)
    except Exception as e:
        logger.error(f"Error searching for files: {e}")
    
    return found_files

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
    
    # Rename the video file and its associated files if found
    if actual_video_path and actual_video_path.name != new_video_filename:
        try:
            logger.debug(f"Renaming video file from {actual_video_path} to {new_video_path}")
            
            # Rename video file
            actual_video_path.rename(new_video_path)
            
            # Get the base filename without extension
            original_base = actual_video_path.stem
            
            # Find and rename the .info.json file if it exists
            json_files = list(output_dir.glob(f"{original_base}.info.json"))
            if json_files:
                json_path = json_files[0]
                new_json_path = output_dir / f"{short_slug}.info.json"
                logger.debug(f"Renaming JSON file from {json_path} to {new_json_path}")
                json_path.rename(new_json_path)
            
            # Find and rename thumbnail files
            # Use our helper function to find image files with the original base name
            image_files = find_files_by_extension(output_dir, original_base, 
                                               [ext[1:] if ext.startswith('.') else ext for ext in IMAGE_EXTENSIONS])
            
            # Rename found thumbnails
            for thumb_path in image_files:
                new_thumb_path = output_dir / f"{short_slug}{thumb_path.suffix}"
                logger.debug(f"Renaming thumbnail from {thumb_path} to {new_thumb_path}")
                thumb_path.rename(new_thumb_path)
            
            # Update the video path for HTML generation
            video_path = new_video_path
            
        except OSError as e:
            logger.error(f"Error renaming files: {e}")
            # Use the original path if renaming failed
            video_path = actual_video_path
    else:
        # Use the original path if we couldn't find the file or rename wasn't needed
        video_path = actual_video_path or (output_dir / new_video_filename)
    
    # Create the HTML description page
    logger.info("Creating HTML description page...")
    html_path = create_html(metadata, str(video_path), str(output_dir), args.standalone)
    html_path = Path(html_path)  # Convert back to Path object
    
    # Determine if we should clean up files (default is yes, unless --keep-all is specified)
    should_cleanup = not args.keep_all
    if should_cleanup:
        files_to_remove = []
        
        # In standalone mode, we can remove the video file because it's embedded in HTML
        if args.standalone:
            # Try to find video files to remove
            video_files = list(output_dir.glob(f"*.{args.format}"))
            for video_file in video_files:
                if video_file.exists():
                    files_to_remove.append(video_file)
        
        # Get the base names we need to check against
        original_base = actual_video_path.stem if actual_video_path else None
        new_base = short_slug
        
        # Find JSON files to remove
        if original_base:
            json_files = list(output_dir.glob(f"{original_base}.info.json"))
            files_to_remove.extend(json_files)
        
        json_files = list(output_dir.glob(f"{new_base}.info.json"))
        files_to_remove.extend(json_files)
        
        # Find thumbnail files to remove
        for base in [original_base, new_base]:
            if base:
                for ext in IMAGE_EXTENSIONS:
                    ext_clean = ext[1:] if ext.startswith('.') else ext
                    image_files = list(output_dir.glob(f"{base}.{ext_clean}"))
                    files_to_remove.extend(image_files)
                    image_files = list(output_dir.glob(f"{base}.{ext_clean.upper()}"))
                    files_to_remove.extend(image_files)
        
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
