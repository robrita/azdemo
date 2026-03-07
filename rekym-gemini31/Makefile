.PHONY: help install install-dev setup-env dev run test test-unit test-contract test-integration \
        test-performance test-cov lint lint-fix format format-check security typecheck \
        pre-commit-install pre-commit-run docker-up docker-down docker-build docker-logs \
        frontend-install frontend-dev frontend-lint frontend-format frontend-build \
        frontend-test frontend-test-e2e frontend-check frontend-ci assign-cosmos-role \
	setup-partners-container setup-configuration-container setup-tracker-container setup-workflow-containers seed-partners clean clean-all check ci

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
	@echo   setup-env           Copy backend/.env.example to backend/.env
	@echo   dev                 Run development server with auto-reload
	@echo   run                 Run production-like server
	@echo   test                Run all tests
	@echo   test-unit           Run unit tests only
	@echo   test-contract       Run contract tests only
	@echo   test-integration    Run integration tests only
	@echo   test-performance    Run performance tests only
	@echo   test-cov            Run tests with coverage report
	@echo   lint                Check code with ruff linter
	@echo   lint-fix            Fix linting issues automatically
	@echo   format              Format code with ruff
	@echo   format-check        Check code formatting without changes
	@echo   security            Run bandit security scan
	@echo   typecheck           Run mypy type checking
	@echo   pre-commit-install  Install pre-commit hooks
	@echo   pre-commit-run      Run pre-commit on all files
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
	@echo   frontend-test-e2e   Run frontend E2E tests (Playwright)
	@echo   assign-cosmos-role   Assign Cosmos DB RBAC role via scripts/assign_cosmos_role.sh
	@echo   setup-partners-container  Create partners container with indexing policy
	@echo   setup-configuration-container  Create configuration container with indexing policy
	@echo   setup-tracker-container  Create tracker-tasks container for Workflow B
	@echo   seed-partners       Seed partners container from sample data (ID=uuid, FORCE=1)
	@echo   clean               Remove build artifacts and caches
	@echo   clean-all           Remove all artifacts including venv
	@echo   check               Run lint, format check, and tests
	@echo   ci                  Run full CI pipeline

##@ Installation

install: ## Install production dependencies
	pip install -e .

install-dev: ## Install with development dependencies
	pip install -e ".[dev]"

setup-env: ## Copy backend/.env.example to backend/.env
	$(PYTHON) -c "import shutil; shutil.copy('backend/.env.example', 'backend/.env')"

##@ Development Server

dev: ## Run development server with auto-reload
# 	$(UVICORN) $(APP) --reload --port $(PORT)
	$(UVICORN) $(APP) --port $(PORT)

run: ## Run production-like server
	$(UVICORN) $(APP) --host 0.0.0.0 --port $(PORT)

##@ Testing

test: ## Run all tests
	$(PYTEST)

test-unit: ## Run unit tests only
	$(PYTEST) backend/tests/unit/

test-contract: ## Run contract tests only
	$(PYTEST) backend/tests/contract/

test-integration: ## Run integration tests only
	$(PYTEST) backend/tests/integration/

test-performance: ## Run performance tests only
	$(PYTEST) backend/tests/performance/

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

##@ Pre-commit

pre-commit-install: ## Install pre-commit hooks
	pre-commit install

pre-commit-run: ## Run pre-commit on all files
	pre-commit run --all-files

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

frontend-test-e2e: ## Run frontend E2E tests (Playwright)
	cd frontend && npm run test:e2e

frontend-check: frontend-lint frontend-build frontend-test ## Run all frontend checks

frontend-ci: frontend-lint frontend-build frontend-test ## Run full frontend CI pipeline

##@ Azure

assign-cosmos-role: ## Assign Cosmos DB RBAC role via scripts/assign_cosmos_role.sh
	bash scripts/assign_cosmos_role.sh

##@ Data

setup-partners-container: ## Create partners container with indexing policy (use THROUGHPUT=N to override)
	$(PYTHON) -m backend.scripts.setup_partners_container $(if $(THROUGHPUT),--throughput $(THROUGHPUT),)

setup-configuration-container: ## Create configuration container with indexing policy (use THROUGHPUT=N to override)
	$(PYTHON) -m backend.scripts.setup_configuration_container $(if $(THROUGHPUT),--throughput $(THROUGHPUT),)

setup-tracker-container: ## Create tracker-tasks container for Workflow B (use THROUGHPUT=N to override)
	$(PYTHON) -m backend.scripts.setup_tracker_container $(if $(THROUGHPUT),--throughput $(THROUGHPUT),)

setup-workflow-containers: ## Create all workflow containers (tasks, audit, comms, cases, etc.)
	$(PYTHON) -m backend.scripts.setup_workflow_containers $(if $(THROUGHPUT),--throughput $(THROUGHPUT),)

seed-partners: ## Seed partners container from sample data (use ID=<uuid> for single record, FORCE=1 to overwrite)
	$(PYTHON) -m backend.scripts.seed_partners $(if $(ID),--id $(ID),) $(if $(FORCE),--force,)

##@ Utilities

clean: ## Remove build artifacts and caches
	$(PYTHON) -c "import shutil; import pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache', 'htmlcov', 'backend/.pytest_cache', 'backend/.ruff_cache']]; pathlib.Path('.coverage').unlink(missing_ok=True)"
	$(PYTHON) -c "import shutil; import pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"

clean-all: clean ## Remove all artifacts including virtual environment
	$(PYTHON) -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"

check: lint format-check test ## Run lint, format check, and tests

ci: lint format-check typecheck test-cov frontend-ci ## Run full CI pipeline
