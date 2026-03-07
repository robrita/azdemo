# Implementation Checklist

Before marking any task as complete, verify every applicable item:

## Code Quality

- [ ] Code follows layered architecture (Route → Service → Repository → Cosmos DB)
- [ ] All Ruff errors are resolved (`make lint`)
- [ ] Code is formatted (`make format-check`)
- [ ] Security scan passed (`make security`)
- [ ] Type checking passed (`make typecheck`)
- [ ] No code duplication (check for reusable patterns in `backend/src/lib/`)
- [ ] Error handling uses typed exceptions from `backend/src/exceptions.py`
- [ ] Logging is added for debugging
- [ ] Logging is sanitized (no secrets, keys, or sensitive payloads)
- [ ] Security best practices followed (input validation, OWASP)
- [ ] Cross-platform compatibility (Windows/Linux) preserved

## API Standards

- [ ] Pydantic schemas defined in `backend/src/schemas/` for request/response
- [ ] Appropriate HTTP status codes used (see `.rules/API_STANDARDS.md`)
- [ ] Error responses use typed exception classes
- [ ] External calls have explicit timeouts and retry handling
- [ ] Auth dependency (`get_current_user`) included on protected routes
- [ ] Tenant isolation enforced via `TenantScopeGuard` for merchant-scoped endpoints

## Async & I/O

- [ ] Use `aiohttp` for HTTP requests, not `requests`
- [ ] Use `asyncio.gather()` for parallel execution, not `ThreadPoolExecutor`
- [ ] Route handlers and I/O functions declared as `async def`

## Cosmos DB

- [ ] All document fields use camelCase (Pydantic aliases)
- [ ] Repository extends `BaseRepository`
- [ ] Queries use parameterized `@name` syntax (no string interpolation)
- [ ] Partition key used where possible for efficient reads

## Workflow & Audit

- [ ] State transitions go through `TransitionGuardService`
- [ ] Every state change produces an audit event via `AuditWriter`
- [ ] Self-approval blocked (Maker ≠ Checker on same case)

## Dependencies

- [ ] `pyproject.toml` updated with exact `==` pins (if changed)

## Documentation & Testing

- [ ] Tests added: happy path, edge cases, error cases
- [ ] Test coverage meets 80% target
- [ ] Endpoint documentation available via FastAPI `/docs` (auto-generated)

## Frontend

> **Mandatory**: After ANY frontend change, run `make frontend-build` (or `cd frontend && npm run build`) and confirm it succeeds before marking work done. A green build is a hard gate — no exceptions.

- [ ] No hardcoded `blue-*` or `indigo-*` classes for brand colors — use `primary-*` tokens
- [ ] Component classes used where available (`.btn-primary`, `.card`, `.badge-*`, etc.)
- [ ] Status/priority maps imported from `theme/tokens.ts` (not duplicated inline)
- [ ] ESLint passes (`make frontend-lint`)
- [ ] Prettier passes (`make frontend-format`)
- [ ] TypeScript compiles and Vite build succeeds (`make frontend-build`)
- [ ] Unit tests pass (`make frontend-test`)
- [ ] No new Tailwind classes that duplicate existing component classes in `index.css`

## Agent Interaction

- [ ] New rules added to AGENTS.md follow the map pattern (one-liner + pointer to `.rules/` topic file)
- [ ] Clarifying questions use plain text with numbered options (no checkbox/radio UI)
- [ ] Any new/changed config key is updated in `.env.example`, mirrored in local `.env`, and reflected in both `local.settings.example.json` and local `local.settings.json` when used by Azure Functions
