.PHONY: install test package clean lint typecheck

# Install sumvideo as a command using uv
install:
	uv tool install .

# Run tests
test:
	./run_tests.py

# Package and upload to PyPI
package: clean
	uv build
	uv publish

# Clean build artifacts
clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/

# Run linting
lint:
	ruff check sumvideo.py

# Run type checking
typecheck:
	mypy --follow-untyped-imports sumvideo.py

# Run both lint and typecheck
check: lint typecheck