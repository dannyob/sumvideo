# SumVideo Project Guidelines

## Virtual Environment
- Virtual environment is located in the `.venv` directory
- Activate: `source .venv/bin/activate`
- Deactivate: `deactivate`

## Commands
- **Run**: `./sumvideo.py [URL] [-o OUTPUT_DIR] [-f FORMAT]`
- **Install dependencies**: `uv pip install jinja2 yt-dlp python-slugify`
- **Lint**: `ruff check sumvideo.py`
- **Type check**: `mypy --follow-untyped-imports sumvideo.py`
- **Run tests**: `./run_tests.py`

## Directory Structure
- **Root**: Contains main program (`sumvideo.py`) and test runner (`run_tests.py`)
- **tests/**: Contains all test files
  - **tests/data/**: Test video files and metadata
  - **tests/output/**: Directory for test output files

## Tests
- All test files should follow the naming pattern `test_*.py`
- Place test files in the `tests/` directory
- Place test data in the `tests/data/` directory
- The test runner will automatically discover and run all test files
- Each test file should be executable (chmod +x)
- Use uv run header for dependency management

## Code Style Guidelines
- **Imports**: Standard library first, then third-party, then local
- **Typing**: Use type hints for all functions (parameters and returns)
- **Docstrings**: Google style with Args/Returns sections
- **Error handling**: Use try/except with specific exceptions
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Function length**: Keep functions focused and under 50 lines
- **Line length**: Maximum 100 characters
- **Whitespace**: 4 spaces for indentation, no tabs
- **Path handling**: Use pathlib.Path for file operations
- **Jinja2 templates**: Maintain consistent indentation in template strings
