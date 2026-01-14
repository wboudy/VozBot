.PHONY: install test dev lint format clean docker-up docker-down help

# Default target
help:
	@echo "VozBot Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install     Install dependencies (pip install -e .[dev])"
	@echo "  test        Run pytest test suite"
	@echo "  dev         Start development server with uvicorn"
	@echo "  lint        Run ruff linter"
	@echo "  format      Format code with ruff"
	@echo "  clean       Remove build artifacts and cache"
	@echo "  docker-up   Start Postgres and Redis containers"
	@echo "  docker-down Stop and remove containers"

# Install dependencies
install:
	pip install -e ".[dev]"

# Run tests
test:
	pytest -v --cov=vozbot --cov-report=term-missing

# Start development server
dev:
	uvicorn vozbot.main:app --reload --host 0.0.0.0 --port 8000

# Run linter
lint:
	ruff check vozbot tests

# Format code
format:
	ruff format vozbot tests
	ruff check --fix vozbot tests

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
