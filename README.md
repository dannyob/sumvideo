# SumVideo

A tool for summarizing and saving video content from URLs.

## Features

- Download videos from various platforms
- Generate HTML summaries with metadata
- Supports different output formats
- Extract video thumbnails and metadata

## Installation

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

### Options

- `URL`: The video URL to summarize
- `-o, --output`: Output directory (default: current directory)
- `-f, --format`: Output format

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

- `sumvideo.py`: Main program
- `run_tests.py`: Test runner
- `tests/`: Test files and data
- `videos/`: Sample videos and output
- `stubs/`: Type stubs