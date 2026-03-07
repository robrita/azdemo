.PHONY: help install install-dev dev run test test-cov lint lint-fix format format-check \
        security typecheck docker-up docker-down docker-build docker-logs \
        frontend-install frontend-dev frontend-lint frontend-format frontend-build \
        frontend-test frontend-ci clean check ci

# Variables
PYTHON := python
PYTEST := pytest
RUFF := ruff
UVICORN := uvicorn
APP := src.main:app
PORT := 8000
export PYTHONPATH := backend

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo.
	@echo Usage: make [target]
	@echo.
	@echo Targets:
	@echo   install             Install production dependencies
	@echo   install-dev         Install with development dependencies
	@echo   dev                 Run development server with auto-reload
	@echo   run                 Run production-like server
	@echo   test                Run all tests
	@echo   test-cov            Run tests with coverage report
	@echo   lint                Check code with ruff linter
	@echo   lint-fix            Fix linting issues automatically
	@echo   format              Format code with ruff
	@echo   format-check        Check code formatting without changes
	@echo   security            Run bandit security scan
	@echo   typecheck           Run mypy type checking
	@echo   docker-up           Start all services with docker compose
	@echo   docker-down         Stop all services
	@echo   docker-build        Build docker images
	@echo   docker-logs         Tail docker compose logs
	@echo   frontend-install    Install frontend dependencies
	@echo   frontend-dev        Start frontend dev server
	@echo   frontend-lint       Lint frontend with ESLint
	@echo   frontend-format     Format frontend with Prettier
	@echo   frontend-build      Build frontend (tsc + vite)
	@echo   frontend-test       Run frontend unit tests (Vitest)
	@echo   frontend-ci         Run full frontend CI pipeline
	@echo   clean               Remove build artifacts and caches
	@echo   check               Run lint, format check, and tests
	@echo   ci                  Run full CI pipeline

##@ Installation

install: ## Install production dependencies
	pip install -e .

install-dev: ## Install with development dependencies
	pip install -e ".[dev]"

##@ Development Server

dev: ## Run development server with auto-reload
	$(UVICORN) $(APP) --reload --port $(PORT)

run: ## Run production-like server
	$(UVICORN) $(APP) --host 0.0.0.0 --port $(PORT)

##@ Testing

test: ## Run all tests
	$(PYTEST)

test-cov: ## Run tests with coverage report
	$(PYTEST) --cov=backend/src --cov-report=html --cov-report=term

##@ Code Quality

lint: ## Check code with ruff linter
	$(RUFF) check backend/

lint-fix: ## Fix linting issues automatically
	$(RUFF) check --fix backend/

format: ## Format code with ruff
	$(RUFF) format backend/

format-check: ## Check code formatting without changes
	$(RUFF) format --check backend/

security: ## Run bandit security scan
	bandit -r backend/src/

typecheck: ## Run mypy type checking
	mypy backend/src/

##@ Docker

docker-up: ## Start all services with docker compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-build: ## Build docker images
	docker compose build

docker-logs: ## Tail docker compose logs
	docker compose logs -f

##@ Frontend

frontend-install: ## Install frontend dependencies
	cd frontend && npm install

frontend-dev: ## Start frontend dev server
	cd frontend && npm run dev

frontend-lint: ## Lint frontend with ESLint
	cd frontend && npm run lint

frontend-format: ## Format frontend with Prettier
	cd frontend && npm run format

frontend-build: ## Build frontend (tsc + vite)
	cd frontend && npm run build

frontend-test: ## Run frontend unit tests (Vitest)
	cd frontend && npm run test

frontend-ci: frontend-lint frontend-build frontend-test ## Run full frontend CI pipeline

##@ Utilities

clean: ## Remove build artifacts and caches
	$(PYTHON) -c "import shutil; import pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache', 'htmlcov', 'backend/.pytest_cache']]; pathlib.Path('.coverage').unlink(missing_ok=True)"
	$(PYTHON) -c "import shutil; import pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"

check: lint format-check test ## Run lint, format check, and tests

ci: check security typecheck ## Run full backend CI pipeline
