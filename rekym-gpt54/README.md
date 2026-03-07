# FastAPI + React + Azure Functions + Cosmos Template

This folder is a portable project template for a full-stack web app that uses FastAPI, React, Vite, Azure Functions v2 ASGI hosting, container deployment, and Azure Cosmos DB as the default primary store.

The template is opinionated. It preserves the engineering standards from the source repository instead of acting like a generic starter. If you copy the contents of this folder into a new repository, the project should still explain how it is meant to be extended and deployed.

## What This Template Includes

- Root-level development workflow with `make` targets.
- Root `.env.example` and working `.env` for backend and Docker Compose.
- Azure Functions `function_app.py` as a thin ASGI hosting adapter.
- Container runtime using the same FastAPI app under `uvicorn`.
- Azure Cosmos DB as the default database, with emulator-first local defaults.
- FastAPI backend with typed settings, DI providers, structured logging, correlation IDs, health probes, service and repository layers, and Cosmos client reuse.
- React + TypeScript + Vite + Tailwind frontend with centralized semantic tokens, shared component classes, dark mode support, and feature-oriented structure.
- Bootstrap scripts, tests, and CI workflow.
- Template-local docs under `.rules/`, plus architecture, tooling, deployment, placeholders, and verification guides.

## Start Here

1. Read `AGENTS.md`.
2. Read `.rules/ARCHITECTURE.md`, `.rules/RUNTIME.md`, `.rules/CONFIG_MANAGEMENT.md`, and `.rules/COSMOS_FIELD_NAMING.md`.
3. Review `structure/project-tree.md`.
4. Run one of the bootstrap scripts in `scripts/`.
5. Start local development with `make dev` and `make frontend-dev`, or `make docker-up` for the full stack.

## Local Runtime Modes

### Root local development

- `make install-dev`
- `make frontend-install`
- `make dev`
- `make frontend-dev`

### Full Docker Compose stack

- `make docker-up`
- `make docker-logs`
- `make docker-down`

### Azure Functions host

- Install `requirements.txt`
- Copy `local.settings.example.json` to `local.settings.json`
- Run `func host start`

## Key Guarantees

- Backend configuration comes from one `Settings(BaseSettings)` source of truth.
- Python dependencies are exact-pinned with `==`.
- Cosmos documents and queries use camelCase serialized field names.
- Route handlers stay thin and delegate into services.
- Cosmos access stays behind repositories.
- The Azure Functions wrapper stays thin and contains no business logic.
- Frontend theming is centralized and dark-mode compatible.
- Health endpoints include `/health`, `/health/live`, and `/health/ready`.
- Docker, local dev, and Functions all read the same backend config model.

## Files To Review First

- `AGENTS.md`
- `.rules/ARCHITECTURE.md`
- `.rules/COSMOS_FIELD_NAMING.md`
- `backend/src/main.py`
- `backend/src/config.py`
- `frontend/src/theme/tokens.ts`
- `frontend/src/index.css`
- `structure/project-tree.md`