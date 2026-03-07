# Implementation Checklist

Before marking any task as complete, verify every applicable item:

## Code Quality

- [ ] Code follows layered architecture (Route → Service → Repository → Cosmos DB)
- [ ] All Ruff errors are resolved (`make lint`)
- [ ] Code is formatted (`make format-check`)
- [ ] Security scan passed (`make security`)
- [ ] Type checking passed (`make typecheck`)
- [ ] No code duplication
- [ ] Error handling uses typed exceptions from `backend/src/exceptions.py`
- [ ] Logging is added for debugging
- [ ] Logging is sanitized (no secrets)
- [ ] Cross-platform compatibility (Windows/Linux) preserved

## API Standards

- [ ] Pydantic schemas defined in `backend/src/schemas/`
- [ ] Appropriate HTTP status codes used
- [ ] Error responses use typed exception classes
- [ ] External calls have explicit timeouts and retry handling

## Async & I/O

- [ ] Use `aiohttp` for HTTP requests, not `requests`
- [ ] Use `asyncio.gather()` for parallel execution
- [ ] Route handlers and I/O functions declared as `async def`

## Cosmos DB

- [ ] All document fields use camelCase (Pydantic aliases)
- [ ] Repository extends `BaseRepository`
- [ ] Queries use parameterized `@name` syntax
- [ ] Partition key used where possible for efficient reads

## Dependencies

- [ ] `pyproject.toml` updated with exact `==` pins (if changed)

## Documentation & Testing

- [ ] Tests added: happy path, edge cases, error cases
- [ ] Test coverage meets 80% target

## Frontend

- [ ] No hardcoded `blue-*` or `indigo-*` classes — use `primary-*` tokens
- [ ] Component classes used where available
- [ ] Status/severity maps imported from `theme/tokens.ts`
- [ ] ESLint passes (`make frontend-lint`)
- [ ] Prettier passes (`make frontend-format`)
- [ ] TypeScript compiles and Vite build succeeds (`make frontend-build`)
- [ ] Unit tests pass (`make frontend-test`)

## Config

- [ ] Any new config key updated in `.env.example`, `Settings`, and `local.settings.example.json`
