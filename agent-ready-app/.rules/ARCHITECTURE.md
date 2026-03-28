# Architecture

## Overview

Full-stack web application with FastAPI backend, React frontend, and Azure Cosmos DB.

**Tech Stack**: Python 3.12+ · FastAPI · Pydantic v2 · Azure Cosmos DB (async SDK) · React + TypeScript · TanStack Query · Vite · Tailwind CSS

## Layered Architecture

```
Request → Route → Service → Repository → Cosmos DB
```

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **Routes** | HTTP handling, request/response mapping | `backend/src/routes/` |
| **Schemas** | Request/Response DTOs (Pydantic) | `backend/src/schemas/` |
| **Services** | Business logic, orchestration | `backend/src/services/` |
| **Repositories** | Data access, Cosmos DB operations | `backend/src/repositories/` |
| **Models** | Domain entities (Pydantic) | `backend/src/models/` |
| **Cosmos** | DB client singleton, container setup | `backend/src/cosmos/` |
| **Middleware** | Auth, rate limiting | `backend/src/middleware/` |
| **Lib** | Shared utilities | `backend/src/lib/` |

**Dependency rule**: Routes → Services → Repositories → Cosmos. Never skip layers.

## Configuration

Key environment variables (see `.env.example` for full annotated list):

| Variable | Description |
|----------|-------------|
| `COSMOS_ENDPOINT` | Cosmos DB endpoint URL |
| `COSMOS_DATABASE` | Database name |
| `COSMOS_AUTH_MODE` | `entra` (default) or `key` (account key) |
| `COSMOS_KEY` | Account key (only when `COSMOS_AUTH_MODE=key`) |
| `APP_ENV` | Environment (development/staging/production) |
| `CORS_ORIGINS` | Allowed CORS origins |

## Frontend Structure

```
frontend/src/
├── main.tsx          # Entry point
├── App.tsx           # Routes and providers
├── index.css         # Theme base + component classes
├── theme/tokens.ts   # Color/status maps
├── components/       # Shared components
├── features/         # Feature modules
├── hooks/            # Custom hooks
├── services/         # API clients
└── types/            # TypeScript types
```

## Deployment Modes

1. **Azure Functions** — `function_app.py` wraps FastAPI via `AsgiFunctionApp`
2. **Container** — same FastAPI app under `uvicorn` in Docker
3. **Local** — `make dev` (backend) + `make frontend-dev` (frontend)
