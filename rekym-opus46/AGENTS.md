# Project Template — Agent Guidelines

Full-stack web application template. FastAPI + React + Azure Cosmos DB.
Azure Functions ASGI hosting + container deployment.
See [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) for system design, layers, and data model.

## Project Context

**This is a greenfield project.** No legacy consumers, no backward-compatibility constraints. Freely update all impacted dependencies, schemas, APIs, and frontend components to best-practice solutions.

## Critical Rules

1. **Async everything** — use `aiohttp`, `asyncio.gather()`, and `async def` handlers. → [.rules/ASYNC_PATTERNS.md](.rules/ASYNC_PATTERNS.md)
2. **Containerized deployment** — runs via Docker Compose (FastAPI + React). → [.rules/RUNTIME.md](.rules/RUNTIME.md)
3. **Pin exact versions in `pyproject.toml`** — use `==` pins for all dependencies. → [.rules/DEPENDENCIES.md](.rules/DEPENDENCIES.md)
4. **Layered architecture** — Route → Service → Repository → Cosmos DB. Never skip layers. → [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md)
5. **Pass all quality gates** — lint, format, security, typecheck, tests (80% coverage). → [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md)
6. **Reuse before writing** — check for existing helpers and patterns first. → [.rules/PATTERNS.md](.rules/PATTERNS.md)
7. **Run the checklist** — verify every applicable item before marking work done. → [.rules/CHECKLIST.md](.rules/CHECKLIST.md)
8. **Text-only human input** — never use checkbox/radio UI; ask questions as plain text with numbered options.
9. **Frontend theme compliance** — use `primary-*` tokens; never hardcode `blue-*`/`indigo-*`. → [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md)
10. **Frontend quality gates** — every frontend change must pass lint, format, typecheck, build, and tests. → [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md)
11. **Cosmos DB camelCase fields** — all document fields are camelCase; escape reserved words with `c["field"]`; no `/id/?` in indexing included paths; singleton IDs use `"{type}:{key}"`. → [.rules/COSMOS_DB.md](.rules/COSMOS_DB.md)
12. **Dark mode compatibility** — every frontend change must render correctly in both light and dark mode; use `dark:` variants. → [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md)
13. **Centralized config with fail-fast validation** — all env vars go through `Settings(BaseSettings)`; never use `os.getenv()` directly. → [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md)
14. **Config parity** — any new/changed config key must be updated in `.env.example`, `local.settings.example.json`, `docker-compose.yaml`, and `Settings`. → [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md)

## Navigation

| Topic | File | When to Read |
|-------|------|-------------|
| System architecture | [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) | Understanding the codebase, adding domains |
| Async patterns | [.rules/ASYNC_PATTERNS.md](.rules/ASYNC_PATTERNS.md) | HTTP calls, parallel operations |
| Quality gates | [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md) | After any code change |
| Frontend theme | [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md) | Adding/modifying frontend components |
| API response format | [.rules/API_STANDARDS.md](.rules/API_STANDARDS.md) | Adding/modifying endpoints |
| Dependencies | [.rules/DEPENDENCIES.md](.rules/DEPENDENCIES.md) | Adding/updating packages |
| Code patterns | [.rules/PATTERNS.md](.rules/PATTERNS.md) | Implementing features |
| Checklist | [.rules/CHECKLIST.md](.rules/CHECKLIST.md) | Before marking any task done |
| Runtime & Docker | [.rules/RUNTIME.md](.rules/RUNTIME.md) | Dev server, Docker, timeouts, logging |
| Cosmos DB | [.rules/COSMOS_DB.md](.rules/COSMOS_DB.md) | Any Cosmos DB work |
| Config management | [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md) | Adding/changing env vars |

## Reading Order for New Tasks

1. This file — get the map
2. [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) — understand the system
3. The topic doc relevant to your task (see Navigation above)
4. [.rules/CHECKLIST.md](.rules/CHECKLIST.md) — verify completeness before finishing

## Self-Governance Rules

1. **AGENTS.md is the map, not the encyclopedia.** Keep it concise. Add detail to topic docs in `.rules/`.
2. **Enforce mechanically when possible.** Promote rules into linter config or CI checks.
3. **Keep docs fresh.** Update topic docs when behavior changes.
