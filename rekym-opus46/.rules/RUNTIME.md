# Runtime & Observability

## Running the Development Stack

### Docker Compose (Full Stack)

```bash
make docker-up      # Start all services
make docker-logs    # View logs
make docker-down    # Stop all services
make docker-build   # Rebuild images
```

Services:
- **Backend**: http://localhost:8000 (FastAPI + uvicorn)
- **Frontend**: http://localhost:5173 (Vite dev server)
- **Cosmos DB**: cloud account configured via `COSMOS_ENDPOINT`

### Local Development (Without Docker)

```bash
make dev              # Backend on port 8000
make frontend-dev     # Frontend on port 5173
```

## Route Handler Structure

Keep FastAPI route handlers thin — delegate to service/business logic layers.

```python
@router.get("/{item_id}")
async def get_item(
    item_id: str,
    item_repo: ItemRepository = Depends(get_item_repo),
) -> dict[str, Any]:
    return await item_repo.read(item_id)
```

## Dependency Injection

Use FastAPI's `Depends()`. All providers live in `backend/src/dependencies.py`.

## Timeouts

Configure explicit timeouts for all external calls.

```python
async with aiohttp.ClientSession() as session:
    async with session.post(
        url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
    ) as response:
        result = await response.json()
```

## Retry Logic

Retry with backoff for transient failures: HTTP 429, timeouts, transient 5xx.

## Client Reuse

Use `CosmosClientManager` singleton via FastAPI lifespan. Never create clients per request.

## Logging

- Use module-level loggers: `logger = logging.getLogger(__name__)`
- Include context in log messages (correlation ID, entity IDs)
- **Never** log secrets, keys, or tokens
- Use structured JSON logs in production

## Health Endpoints

- `/health` — basic liveness
- `/health/live` — liveness probe
- `/health/ready` — readiness (checks Cosmos DB connectivity)

## Cross-Platform Compatibility

All code and scripts must work on both Windows and Linux:
- Use `pathlib.Path` for file/path operations
- Avoid shell-specific assumptions
- Keep line endings platform-agnostic
