.PHONY: help install install-dev dev run lint format format-check typecheck test check \
	frontend-install frontend-dev frontend-lint frontend-format frontend-build frontend-test frontend-ci \
	docker-up docker-down docker-build docker-logs bootstrap ci

PYTHON := python
PIP := $(PYTHON) -m pip
PYTEST := pytest
RUFF := ruff
MYPY := mypy
UVICORN := uvicorn
APP := src.main:app
PORT := 8000
export PYTHONPATH := backend

.DEFAULT_GOAL := help

help:
	@echo Available targets:
	@echo   install install-dev dev run lint format format-check typecheck test check
	@echo   frontend-install frontend-dev frontend-lint frontend-format frontend-build frontend-test frontend-ci
	@echo   docker-up docker-down docker-build docker-logs bootstrap ci

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

dev:
	$(UVICORN) $(APP) --reload --port $(PORT)

run:
	$(UVICORN) $(APP) --host 0.0.0.0 --port $(PORT)

lint:
	$(RUFF) check backend/src backend/tests function_app.py

format:
	$(RUFF) format backend/src backend/tests function_app.py

format-check:
	$(RUFF) format --check backend/src backend/tests function_app.py

typecheck:
	$(MYPY) backend/src

test:
	$(PYTEST) backend/tests

check: lint format-check typecheck test

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-lint:
	cd frontend && npm run lint

frontend-format:
	cd frontend && npm run format

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npm run test

frontend-ci: frontend-lint frontend-build frontend-test

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f

bootstrap:
	@echo Run scripts/bootstrap.ps1 on Windows or scripts/bootstrap.sh on Linux/macOS.

ci: check frontend-ci