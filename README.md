# SumVideo

A command-line tool for downloading videos and generating rich HTML preview pages with embedded metadata and thumbnails.

## Features

- **Video Download**: Download videos from YouTube and other platforms using yt-dlp
- **HTML Generation**: Create beautiful HTML pages with embedded video player
- **Rich Previews**: Generate pages with Open Graph and Twitter Card metadata for social sharing
- **Thumbnail Extraction**: Automatically extract and embed video thumbnails
- **Metadata Preservation**: Capture and display video title, description, upload date, and duration
- **Multiple Formats**: Support for various video formats (mp4, webm, ogg, mov)
- **Smart Naming**: Generate SEO-friendly filenames using slugified titles and dates

## Requirements

- Python 3.12 or higher
- uv (for dependency management)

## Installation

### Using uv (Recommended)

The script uses inline dependency management with uv:

```bash
# Make the script executable
chmod +x sumvideo.py

# Run directly - uv will handle dependencies automatically
./sumvideo.py [URL]
```

### Manual Installation

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install jinja2 yt-dlp python-slugify
```

## Usage

```bash
./sumvideo.py [URL] [-o OUTPUT_DIR] [-f FORMAT]
```

### Arguments

- `URL`: The video URL to download (required)

### Options

- `-o, --output-dir`: Output directory (default: current directory)
- `-f, --format`: Video format to download (default: mp4)
  - Supported formats: mp4, webm, ogg, mov
- `--standalone`: Create a standalone HTML file with embedded video and metadata
- `--keep-all`: Keep all downloaded files (default is to clean up temporary files)
- `-v, --verbose`: Enable verbose logging for debugging
- `-h, --help`: Show help message and exit

### Examples

```bash
# Download a video to the current directory
./sumvideo.py https://www.youtube.com/watch?v=example

# Download to a specific directory
./sumvideo.py https://www.youtube.com/watch?v=example -o ./videos

# Download in webm format
./sumvideo.py https://www.youtube.com/watch?v=example -f webm

# Create a standalone HTML with embedded video
./sumvideo.py --standalone https://vimeo.com/123456789

# Download with verbose logging
./sumvideo.py -v https://www.youtube.com/watch?v=example

# Keep all temporary files
./sumvideo.py --keep-all https://www.youtube.com/watch?v=example
```

### Output

For each video, SumVideo creates:
- Video file: `[slug].[format]` (e.g., `my-video-2024-07-08.mp4`)
- HTML page: `[slug].html` with embedded video player and metadata
- Thumbnail: Embedded as base64 in the HTML for portability

## Development

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd sumvideo

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install jinja2 yt-dlp python-slugify
```

### Testing

```bash
# Run all tests
./run_tests.py
```

### Code Quality

```bash
# Lint code
ruff check sumvideo.py

# Type check
mypy --follow-untyped-imports sumvideo.py
```

## Project Structure

```
sumvideo/
├── sumvideo.py          # Main program with inline dependencies
├── run_tests.py         # Test runner script
├── tests/               # Test directory
│   ├── data/           # Test video files and metadata
│   ├── output/         # Test output directory
│   ├── test_sumvideo.py # Unit tests
│   └── test_with_real_video.py # Integration tests
├── videos/              # Default output directory (created on first use)
├── stubs/               # Type stubs for dependencies
├── CLAUDE.md           # Project guidelines and coding standards
└── README.md           # This file
```

## Dependencies

SumVideo uses the following Python packages:
- **jinja2**: HTML template rendering
- **yt-dlp**: Video downloading from various platforms
- **python-slugify**: URL-friendly filename generation

## License

[Add your license information here]