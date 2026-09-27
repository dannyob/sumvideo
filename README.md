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
- `--tag TAG`: Tag the page. Repeat for more than one tag.
- `--index`: Write `index.html` listing every SumVideo page in the output
  directory, newest first. The URL is optional with `--index`: without one,
  SumVideo just rebuilds the index.
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

# Download, then rebuild the index of the output directory
./sumvideo.py --index https://www.youtube.com/watch?v=example

# Only rebuild the index
./sumvideo.py --index
```

### Tags

Each tag is stored as its own line in the page's `<head>`:

```html
<meta property="video:tag" content="music">
```

To re-tag a page, add or delete these lines (by hand, or with `sed`), then
rebuild the index with `sumvideo --index`. The index lists every tag with a
count, and each tag links to `index.html#tag-<name>`, which shows only the
videos with that tag. The filtering is done in CSS with `:target`, so it
works without JavaScript and filtered views can be bookmarked.

Each page also shows its tags, linked to that filtered view of the index.
They sit between `<!-- sumvideo:tags ... -->` markers, and `--index`
rewrites that block from the `video:tag` lines, so don't edit it directly.
Only pages whose block is out of date are rewritten. When
`SUMVIDEO_BASE_URL` applies the links are absolute; standalone pages made
without it show their tags as plain text.

### Environment variables

- `XDG_VIDEOS_DIR`, then `SUMVIDEO_DIR`: default output directory when `-o` isn't
  given. If neither is set, files go in `./videos/`.
- `SUMVIDEO_BASE_URL`: the public URL where the default output directory is
  served, if you publish it on the web. When set, pages get absolute `og:image`
  and `og:url` links, which link previews need, and SumVideo prints the page's
  public URL when it finishes. It is ignored when `-o` points somewhere other
  than the default output directory.

```bash
export SUMVIDEO_DIR=~/www/videos
export SUMVIDEO_BASE_URL=https://example.com/videos/
sumvideo https://www.youtube.com/watch?v=example
# ...
# Public URL: https://example.com/videos/example-video-0101.html
```

### Output

For each video, SumVideo creates:
- Video file: `[slug].[format]` (e.g., `my-video-2024-07-08.mp4`)
- HTML page: `[slug].html` with embedded video player and metadata
- Thumbnail: `[slug].jpg`, used as the video poster and the `og:image`
  preview image

With `--standalone`, the video and thumbnail are embedded in the HTML page
instead, and the page has no `og:image` (link previews can't use an embedded
image).

## Web front end

`web/sumvideo_web.py` is a small web page for sumvideo: paste a URL and get
back a standalone HTML page to view or download. Tick "Also publish to the
archive" to also save the video to `SUMVIDEO_DIR` and rebuild the index. Jobs
run one at a time using the installed `sumvideo` command.

It listens on `127.0.0.1` only and has no login of its own, so put it behind
something that controls access. For example, to serve it on a Tailscale
network under `/sumvideo/`:

```bash
SUMVIDEO_WEB_PREFIX=/sumvideo/ ./web/sumvideo_web.py
tailscale serve --bg --set-path /sumvideo/ http://127.0.0.1:8765
```

`web/sumvideo-web.service` runs it as a systemd user service; see the comments
in that file and `web/sumvideo-web.env.example`.

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

GPLv3
