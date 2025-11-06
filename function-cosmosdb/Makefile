# Makefile for Azure Functions + Cosmos DB Project
# Note: On Windows, you may need to install 'make' via chocolatey or use WSL
# Requires: uv (https://github.com/astral-sh/uv)

.PHONY: lint run start check-and-run format install test test-unit test-integration test-cov test-fast clean push revert help func-start

# Default target
help:
	@echo "Available commands:"
	@echo "  make lint          - Run Ruff linter"
	@echo "  make format        - Auto-fix linting issues and format code"
	@echo "  make run           - Start Azure Functions host (alias: start, func-start)"
	@echo "  make start         - Start Azure Functions host (alias: run)"
	@echo "  make func-start    - Start Azure Functions host (alias: run)"
	@echo "  make check-and-run - Run linter, then start function host (stops if linting fails)"
	@echo "  make install       - Install dependencies using uv"
	@echo "  make clean         - Clean Python cache files and directories"
	@echo "  make push          - Stage, commit, and push changes (prompts for commit message)"
	@echo "  make revert        - Revert changes and clean temp files"
	@echo ""
	@echo "Testing commands:"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run only unit tests (fast, no Azure services)"
	@echo "  make test-integration - Run only integration tests (requires Azure credentials)"
	@echo "  make test-cov      - Run tests with coverage report"
	@echo "  make test-fast     - Run only fast tests (skip slow and integration)"

# Run linter
lint:
	@echo "🔍 Running Ruff linter..."
	uv run ruff check .

# Auto-fix and format
format:
	@echo "✨ Formatting code with Ruff..."
	uv run ruff check --fix .
	uv run ruff format .

# Start Azure Functions host
run:
	@echo "🚀 Starting Azure Functions host..."
	func start

# Aliases for run
start: run
func-start: run

# Check linting then run (main workflow)
check-and-run: lint
	@echo "✅ Linting passed! Starting Azure Functions host..."
	func start

# Install dependencies
install:
	@echo "📦 Installing dependencies with uv..."
	uv sync

# Clean Python cache and temporary files
clean:
	@echo "🧹 Cleaning cache and temporary files..."
ifeq ($(OS),Windows_NT)
	@powershell -Command "Get-ChildItem -Path . -Include __pycache__,*.pyc,.pytest_cache,.ruff_cache,.mypy_cache -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
	@echo "✅ Cleaned Python cache files"
else
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned Python cache files"
endif

# Run all tests
test:
	@echo "🧪 Running all tests..."
	uv run pytest

# Run only unit tests (fast, no external dependencies)
test-unit:
	@echo "🧪 Running unit tests..."
	uv run pytest -m unit -v

# Run only integration tests (requires Azure credentials)
test-integration:
	@echo "🧪 Running integration tests..."
	uv run pytest -m integration -v

# Run tests with coverage report
test-cov:
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=. --cov-report=term-missing --cov-report=html

# Run fast tests only (skip slow and integration tests)
test-fast:
	@echo "🧪 Running fast tests..."
	uv run pytest -m "not slow and not integration" -v

# Stage, commit, and push changes (cross-platform)
push:
ifeq ($(OS),Windows_NT)
	@powershell -Command "$$msg = Read-Host 'Enter commit message'; if ($$msg) { git add . ; git commit -m \"$$msg\" ; git push } else { Write-Host 'Commit cancelled - no message provided' -ForegroundColor Yellow }"
else
	@read -p "Enter commit message: " msg; \
	if [ -n "$$msg" ]; then \
		git add . && \
		git commit -m "$$msg" && \
		git push; \
	else \
		echo "Commit cancelled - no message provided"; \
	fi
endif

# Revert changes and clean temp files (cross-platform)
revert:
ifeq ($(OS),Windows_NT)
	@powershell -Command "if (Test-Path local.settings.json) { git restore local.settings.json -ErrorAction SilentlyContinue }; Write-Host '✅ Reverted local.settings.json if changed'"
else
	@if [ -f local.settings.json ]; then git restore local.settings.json 2>/dev/null || true; fi
	@echo "✅ Reverted local.settings.json if changed"
endif
