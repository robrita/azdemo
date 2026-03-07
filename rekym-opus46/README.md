# Full-Stack Web App Template

Portable, reproducible project template for building **FastAPI + React + Azure Cosmos DB** applications with Azure Functions ASGI hosting and container deployment support.

## What's Included

| Area | What You Get |
|------|-------------|
| **Backend** | FastAPI, async-first, layered architecture (Route → Service → Repository → Cosmos DB) |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS with centralized semantic theme |
| **Data Store** | Azure Cosmos DB (async SDK, singleton client, camelCase fields) |
| **Hosting** | Azure Functions v2 ASGI adapter + container deployment via Docker Compose |
| **Config** | Centralized `Settings(BaseSettings)`, fail-fast validation, env parity |
| **Quality** | Ruff, mypy, Bandit, pytest, ESLint, Prettier, Vitest, Playwright |
| **CI** | GitHub Actions workflow with backend + frontend quality gates |

## Quick Start

```bash
# 1. Copy template into a new project
cp -r template/ ../my-new-app/
cd ../my-new-app/

# 2. Run bootstrap
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh

# 3. Start the full stack (Docker)
make docker-up

# 4. Or start locally (no Docker)
make install-dev        # Backend deps
make frontend-install   # Frontend deps
make dev                # Backend on :8000
make frontend-dev       # Frontend on :5173
```

## Project Structure

```
├── AGENTS.md                     # Agent guidelines (rules map)
├── .rules/                       # Detailed rule docs
├── Makefile                      # All dev/CI/Docker targets
├── docker-compose.yaml           # Full-stack local runtime
├── pyproject.toml                # Backend deps (exact pins)
├── requirements.txt              # Azure Functions packaging
├── function_app.py               # Azure Functions ASGI adapter
├── host.json                     # Azure Functions host config
├── .env.example                  # Backend env template
├── local.settings.example.json   # Azure Functions env template
├── backend/
│   ├── Dockerfile
│   └── src/
│       ├── main.py               # FastAPI app + lifespan
│       ├── config.py             # Settings(BaseSettings)
│       ├── exceptions.py         # Typed exception hierarchy
│       ├── dependencies.py       # DI container
│       ├── cosmos/
│       │   └── client.py         # Singleton CosmosClientManager
│       ├── routes/               # Thin route handlers
│       ├── schemas/              # Pydantic request/response DTOs
│       ├── services/             # Business logic
│       ├── repositories/         # Data access (BaseRepository)
│       ├── models/               # Domain entities
│       ├── middleware/           # Auth, rate limiting
│       └── lib/                  # Shared utilities
├── frontend/
│   ├── Dockerfile
│   ├── .env.example
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css             # Theme base + component classes
│       ├── theme/tokens.ts       # Color/status maps
│       ├── components/           # Shared components
│       ├── features/             # Feature modules
│       ├── hooks/                # Custom hooks
│       ├── services/             # API clients
│       └── types/                # TypeScript types
├── .github/workflows/ci.yml     # CI pipeline
└── scripts/
    └── bootstrap.sh              # One-command project setup
```

## Deployment Modes

### 1. Azure Functions (ASGI)

`function_app.py` wraps the FastAPI app via `AsgiFunctionApp`. No business logic in the wrapper — it's a thin hosting adapter.

```bash
func start   # Local Azure Functions runtime
```

### 2. Container (Docker Compose / AKS / App Service)

Same FastAPI app runs under `uvicorn` in a container.

```bash
make docker-up   # Docker Compose
```

### 3. Local Development

```bash
make dev            # uvicorn with auto-reload on :8000
make frontend-dev   # Vite dev server on :5173
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Agent rules map |
| [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) | Layered architecture |
| [.rules/ASYNC_PATTERNS.md](.rules/ASYNC_PATTERNS.md) | Async conventions |
| [.rules/API_STANDARDS.md](.rules/API_STANDARDS.md) | API response format |
| [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md) | Env var management |
| [.rules/COSMOS_DB.md](.rules/COSMOS_DB.md) | Cosmos DB conventions |
| [.rules/DEPENDENCIES.md](.rules/DEPENDENCIES.md) | Dependency pinning |
| [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md) | Theme & styling |
| [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md) | Quality checks |
| [.rules/RUNTIME.md](.rules/RUNTIME.md) | Runtime & observability |
| [.rules/CHECKLIST.md](.rules/CHECKLIST.md) | Pre-completion checklist |

## Non-Negotiable Rules

1. **Async everything** — `async def`, `aiohttp`, `asyncio.gather()`
2. **Layered architecture** — Route → Service → Repository → Cosmos DB
3. **Centralized config** — single `Settings(BaseSettings)`, no `os.getenv()`
4. **Exact dependency pins** — `==` versions in `pyproject.toml`
5. **Cosmos DB camelCase** — all document fields use camelCase aliases
6. **Thin route handlers** — delegate to services via `Depends()`
7. **Typed exceptions** — never return raw `JSONResponse` for errors
8. **Quality gates** — lint, format, security, typecheck, test, build
9. **Dark mode** — all frontend changes must work in light and dark mode
10. **Config parity** — `.env.example`, `local.settings.example.json`, `Settings`, `docker-compose.yaml` stay in sync
