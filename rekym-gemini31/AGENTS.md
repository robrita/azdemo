# Re-KYM Compliance Platform — Agent Guidelines

GCash Re-KYM centralized compliance platform. Maker-Checker workflow for merchant KYM re-verification.
FastAPI + Azure Cosmos DB backend, React + TypeScript frontend.
See [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) for system design, layers, and data model.

## Project Context

**This is a greenfield development project.** There are no legacy consumers, no backward-compatibility constraints, and no migration obligations. When implementing or modifying features, freely update all impacted dependencies, schemas, APIs, database models, and frontend components to the best-practice solution. Prefer the latest stable patterns over preserving old interfaces.

## Critical Rules

1. **Async everything** — use `aiohttp`, `asyncio.gather()`, and `async def` handlers. → [.rules/ASYNC_PATTERNS.md](.rules/ASYNC_PATTERNS.md)
2. **Containerized deployment** — runs via Docker Compose (FastAPI + React). → [.rules/RUNTIME.md](.rules/RUNTIME.md)
3. **Pin exact versions in `pyproject.toml`** — use `==` pins for all dependencies. → [.rules/DEPENDENCIES.md](.rules/DEPENDENCIES.md)
4. **Layered architecture** — Route → Service → Repository → Cosmos DB. Never skip layers. → [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md)
5. **Pass all quality gates** — lint, format, security, typecheck, tests (80% coverage). → [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md)
6. **Reuse before writing** — check for existing helpers and patterns first. → [.rules/PATTERNS.md](.rules/PATTERNS.md)
7. **Run the checklist** — verify every applicable item before marking work done. → [.rules/CHECKLIST.md](.rules/CHECKLIST.md)
8. **Text-only human input** — never use checkbox/radio UI; ask questions as plain text with numbered options. → [.rules/AGENT_INTERACTION.md](.rules/AGENT_INTERACTION.md)
9. **Date-stamped feature branches** — name branches `feature/<topic>-<YYYY-MM-DD>`, always merge to main before branching. → [.rules/BRANCHING.md](.rules/BRANCHING.md)
10. **Frontend theme compliance** — use `primary-*` tokens of the GCash theme and component classes; never hardcode `blue-*`/`indigo-*`. → [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md)
11. **Frontend quality gates** — every frontend change must pass lint, format, typecheck, **build** (`make frontend-build`), and tests before completion. The build must actually be executed and succeed — never skip it. → [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md)
12. **Cosmos DB camelCase fields, reserved words, indexing guards, and singleton IDs** — all document fields are camelCase; escape reserved words with `c["field"]` (never `c.[field]`); never include `/id/?` in indexing policy included paths (system property); singleton config documents must use `"{type}:{key}"` as `id` (never `"default"`). → [.rules/COSMOS_FIELD_NAMING.md](.rules/COSMOS_FIELD_NAMING.md)
13. **Dark mode compatibility** — every frontend change must render correctly in both light and dark mode; use `dark:` variants for all hardcoded colors. → [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md#dark-mode)
14. **Always recommend an option** — when asking clarifying questions, include a recommended choice with a brief rationale based on project conventions, security, and software-engineering best practices. → [.rules/AGENT_INTERACTION.md](.rules/AGENT_INTERACTION.md)
15. **Always show "Start Implementation" in Plan mode** — when Copilot is in Plan mode, always end the response with a `[Start Implementation]` button so the user can proceed to execution without switching modes manually.
16. **Observability baseline is mandatory** — enforce JSON structured logs, correlation ID propagation, request/exception logging, strict `/health/ready`, frontend error telemetry intake, and Azure App Insights export wiring. → [.rules/RUNTIME.md](.rules/RUNTIME.md)
17. **Configuration parity is mandatory** — any new/changed config key must be updated in `.env.example`, mirrored in local `.env`, and reflected in both `local.settings.example.json` and local `local.settings.json` when used by Azure Functions. Never commit secrets in `.env`. → [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md)
18. **Centralized config with fail-fast validation** — all env vars go through a single `Settings(BaseSettings)` class; never use `os.getenv()` directly. Startup validation blocks unsafe config (e.g. debug/disabled-auth in production). → [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md)

## Navigation

| Topic | File | When to Read |
|-------|------|-------------|
| System architecture | [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) | Understanding the codebase, adding domains |
| Async patterns | [.rules/ASYNC_PATTERNS.md](.rules/ASYNC_PATTERNS.md) | HTTP calls, parallel operations |
| Quality gates | [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md) | After any code change (backend or frontend) |
| Frontend theme & styling | [.rules/FRONTEND_THEME.md](.rules/FRONTEND_THEME.md) | Adding or modifying frontend components |
| API response format | [.rules/API_STANDARDS.md](.rules/API_STANDARDS.md) | Adding or modifying endpoints |
| Dependency management | [.rules/DEPENDENCIES.md](.rules/DEPENDENCIES.md) | Adding or updating packages |
| Code patterns & helpers | [.rules/PATTERNS.md](.rules/PATTERNS.md) | Implementing features, removing features |
| Pre-completion checklist | [.rules/CHECKLIST.md](.rules/CHECKLIST.md) | Before marking any task done |
| Quality scoring | [.rules/QUALITY_SCORE.md](.rules/QUALITY_SCORE.md) | Reviewing gaps, planning improvements |
| Execution plans | [.rules/exec-plans/README.md](.rules/exec-plans/README.md) | Complex multi-step work |
| Runtime & observability | [.rules/RUNTIME.md](.rules/RUNTIME.md) | Dev server, Docker, timeouts, retry, logging, correlation IDs, health probes, telemetry |
| Agent interaction | [.rules/AGENT_INTERACTION.md](.rules/AGENT_INTERACTION.md) | Asking clarifying questions, capturing user input |
| Cosmos DB best practices | [.github/skills/cosmosdb-best-practices/SKILL.md](.github/skills/cosmosdb-best-practices/SKILL.md) | Any Cosmos DB work |
| Cosmos DB field naming | [.rules/COSMOS_FIELD_NAMING.md](.rules/COSMOS_FIELD_NAMING.md) | Indexing policies, excluded paths, queries |
| Branching strategy | [.rules/BRANCHING.md](.rules/BRANCHING.md) | Creating feature branches, merging to main |
| Config & env var management | [.rules/CONFIG_MANAGEMENT.md](.rules/CONFIG_MANAGEMENT.md) | Adding, changing, or removing env vars |

## Reading Order for New Tasks

1. This file (you're here) — get the map
2. [.rules/ARCHITECTURE.md](.rules/ARCHITECTURE.md) — understand the system
3. The topic doc relevant to your task (see Navigation above)
4. [.rules/CHECKLIST.md](.rules/CHECKLIST.md) — verify completeness before finishing

## Runtime & Observability

Thin route handlers, explicit timeouts, retry with backoff, singleton Cosmos client, structured logs with correlation IDs, strict readiness checks, and telemetry export wiring. → [.rules/RUNTIME.md](.rules/RUNTIME.md)

## Self-Governance Rules

1. **AGENTS.md is the map, not the encyclopedia.** Keep it under 120 lines. Add detail to a topic doc in `.rules/` and only add a one-liner pointer here. New rules require a topic doc in `.rules/`; never add multi-line detail inline.
2. **Enforce mechanically when possible.** When a rule can be checked by a linter, promote it from documentation into code (see custom lint error messages in [.rules/QUALITY_GATES.md](.rules/QUALITY_GATES.md)).
3. **Keep docs fresh.** If you change behavior covered by a topic doc, update the doc in the same PR. Stale docs are worse than no docs.
4. **Track quality.** After addressing a gap, update the grade in [.rules/QUALITY_SCORE.md](.rules/QUALITY_SCORE.md).
5. **Use execution plans for complex work.** Create a plan in [.rules/exec-plans/active/](.rules/exec-plans/active/) before starting multi-step tasks. Move to `completed/` when done.
