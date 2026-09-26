# SumVideo Project Guidelines

## Virtual Environment
- Virtual environment is located in the `.venv` directory
- Activate: `source .venv/bin/activate`
- Deactivate: `deactivate`
- **Note**: The script uses inline dependency management with uv, so it can run without activating the virtual environment

## Commands

### Running the Script
```bash
./sumvideo.py [URL] [OPTIONS]
```

**Options:**
- `-o, --output-dir OUTPUT_DIR` - Directory to save video and HTML files
- `-f, --format FORMAT` - Video format (mp4, webm, ogg, mov) [default: mp4]
- `--style STYLE` - Visual style for HTML page (newyork, bubblegum, default) [default: newyork]
- `--standalone` - Create standalone HTML with embedded video and metadata
- `--keep-all` - Keep all downloaded files (default is to clean up JSON and thumbnails)
- `-v, --verbose` - Enable verbose logging
- `--cookies-from-browser BROWSER` - Extract cookies from browser (chrome, firefox, safari, etc.)
- `--cookies FILE` - Path to Netscape format cookie file

### Development Commands
- **Install as tool**: `make install` or `uv tool install .`
- **Install dependencies**: `uv pip install jinja2 yt-dlp python-slugify`
- **Lint**: `make lint` or `ruff check sumvideo.py run_tests.py tests/`
- **Type check**: `make typecheck` or `mypy --follow-untyped-imports sumvideo.py`
- **Run both**: `make check`
- **Run tests**: `make test` or `./run_tests.py`
- **Build package**: `make package`
- **Clean build artifacts**: `make clean`

### Environment Variables
- **XDG_VIDEOS_DIR** - Default output directory (checked first)
- **SUMVIDEO_DIR** - Alternative default output directory (checked second)
- If neither is set, outputs to `./videos/` in current directory
- **SUMVIDEO_BASE_URL** - Public URL where the default output directory is served.
  Makes `og:image`/`og:url` absolute and prints the page's public URL. Ignored when
  `-o` points elsewhere. Never commit a real value (use `https://example.com/...` in docs/tests)

## Directory Structure
- **Root**: Contains main program (`sumvideo.py`) and test runner (`run_tests.py`)
- **tests/**: Contains all test files
  - **tests/data/**: Test video files and metadata
  - **tests/output/**: Directory for test output files
  - **tests/test_sumvideo.py**: Unit tests
  - **tests/test_with_real_video.py**: Integration tests
- **dist/**: Distribution builds (created by `make package`)
- **stubs/**: Type stubs for dependencies
- **backups/**: Backup files
- **videos/**: Default output directory (created on first use)
- **Makefile**: Build and development tasks
- **pyproject.toml**: Project metadata and dependencies

## Tests
- All test files should follow the naming pattern `test_*.py`
- Place test files in the `tests/` directory
- Place test data in the `tests/data/` directory
- The test runner will automatically discover and run all test files
- Each test file should be executable (chmod +x)
- Use uv run header for dependency management

## Key Features
- **Inline Dependencies**: Script uses uv's inline dependency management (PEP 723)
  - Dependencies declared in script header with `# /// script` block
  - Runs without separate requirements.txt or manual pip install
- **Smart Filename Generation**: Uses slugification with truncation (40 chars) and date suffix
- **Title Cleaning**: Automatically removes social media hashtags from titles
- **Standalone Mode**: Can embed video and JSON metadata directly in HTML as base64
- **Cleanup Behavior**:
  - Default: Removes JSON metadata, keeps video file and thumbnail (converted to JPEG)
  - Standalone mode: Removes all files (video embedded in HTML)
  - `--keep-all` flag: Keeps everything
- **Cookie Support**: Can extract cookies from browsers for authenticated downloads
- **Modular Styling System**: Multiple visual styles available via `--style` argument
  - **newyork** (default): Classic editorial style, serif typography (Merriweather/Lato), formal and elegant
  - **bubblegum**: Soft pastel colors, rounded corners, gradients, modern fonts (Poppins/Quicksand)
  - **default**: Classic simple styling with minimal CSS
  - New styles can be easily added to the `STYLES` dictionary in `sumvideo.py`

## Code Style Guidelines
- **Imports**: Standard library first, then third-party, then local
- **Typing**: Use type hints for all functions (parameters and returns)
  - Use built-in generics and `|` (Python 3.12+): `str | Path` for file path
    parameters, `Type | None` for nullable returns, `dict[str, Any]` for JSON-like
    metadata structures
- **Docstrings**: Google style with Args/Returns sections
- **Error handling**: Use try/except with specific exceptions
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Function length**: Keep functions focused and under 50 lines
- **Line length**: Maximum 100 characters
- **Whitespace**: 4 spaces for indentation, no tabs
- **Path handling**: Use pathlib.Path for file operations
  - Convert string paths to Path objects early in functions
  - Use Path methods (.stem, .suffix, .exists(), etc.)
- **Jinja2 templates**: Maintain consistent indentation in template strings
- **Logging**: Use the logger instance, not print() for status messages
  - Use appropriate log levels (DEBUG, INFO, ERROR)
  - Print to stdout only for final user-facing summaries
- **Constants**: Define at module level in UPPER_SNAKE_CASE
