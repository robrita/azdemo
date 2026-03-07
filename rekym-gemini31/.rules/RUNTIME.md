# Runtime & Observability

Guidelines for application structure, timeouts, retry logic, client management, and logging.

## Running the Development Stack

### Docker Compose (Full Stack)

```bash
# Start all services (backend + frontend)
make docker-up

# View logs
make docker-logs

# Stop all services
make docker-down

# Rebuild images after Dockerfile changes
make docker-build
```

Services:
- **Backend**: http://localhost:8000 (FastAPI + uvicorn)
- **Frontend**: http://localhost:5173 (Vite dev server)
- **Cosmos DB**: cloud account configured via `COSMOS_ENDPOINT`

### Local Development (Without Docker)

```bash
# Backend (uvicorn with auto-reload)
make dev                # Starts on port 8000

# Frontend (Vite dev server)
make frontend-dev       # Starts on port 5173
```

### Prerequisites

1. Python 3.12+ with `uv` or `pip`
2. Node.js 18+ with npm
3. Backend dependencies: `make install-dev`
4. Frontend dependencies: `make frontend-install`
5. Environment variables: copy `backend/.env.example` to `backend/.env`

### Quick Smoke Tests

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

## Route Handler Structure

Keep FastAPI route handlers thin — delegate to service/business logic layers.

```python
# ✅ CORRECT: Thin handler, logic delegated to service/repo
@router.post("/trigger", status_code=201)
async def trigger_case(
    body: TriggerRequest,
    user: AuthUser = Depends(get_current_user),
    case_repo: CaseRepository = Depends(get_case_repo),
    audit_writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    # Validation + delegation + return
    ...

# ❌ WRONG: Business logic inside the handler
@router.post("/trigger", status_code=201)
async def trigger_case(body: TriggerRequest) -> dict[str, Any]:
    container = cosmos_client.get_container("cases")
    query = "SELECT * FROM c WHERE c.merchantId = @mid"
    items = [item async for item in container.query_items(query)]
    # ... 50 more lines of logic ...
```

## Dependency Injection

Use FastAPI's `Depends()` for clean dependency wiring. All providers live in `backend/src/dependencies.py`:

```python
from src.dependencies import get_case_repo, get_audit_writer, get_tenant_guard

@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: AuthUser = Depends(get_current_user),
    case_repo: CaseRepository = Depends(get_case_repo),
    tenant_guard: TenantScopeGuard = Depends(get_tenant_guard),
) -> dict[str, Any]:
    ...
```

## Timeouts

Configure explicit timeouts for all external calls (Cosmos DB, Google Drive, Partner DB, email).

```python
# ✅ CORRECT: Explicit timeout
async with aiohttp.ClientSession() as session:
    async with session.post(
        url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
    ) as response:
        result = await response.json()

# ❌ WRONG: No timeout — can hang indefinitely
async with aiohttp.ClientSession() as session:
    async with session.post(url, json=payload) as response:
        result = await response.json()
```

## Retry Logic

Apply retry logic for transient failures: HTTP 429 (Rate Limit), timeouts, and transient 5xx errors.

```python
# ✅ CORRECT: Retry with backoff for Cosmos DB 429
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        result = await execute_request()
        break
    except CosmosHttpResponseError as e:
        if e.status_code == 429 and attempt < MAX_RETRIES - 1:
            headers_attr: Any = getattr(e, "headers", {})
            error_headers = cast(dict[str, Any], headers_attr)
            retry_after = float(error_headers.get("x-ms-retry-after-ms", 1000)) / 1000.0
            await asyncio.sleep(retry_after)
            continue
        raise
```

## Client Reuse

Use the `CosmosClientManager` singleton via FastAPI lifespan. Never create clients per request.

```python
# ✅ CORRECT: Singleton via lifespan + dependency injection
# Initialized once in main.py lifespan, accessed via app.state
cosmos_manager = request.app.state.cosmos_manager
database = cosmos_manager.database

# ❌ WRONG: New client per request
async def handle_request():
    client = CosmosClient(endpoint, credential)  # created every call
```

## Logging

Use module-level loggers. Include context in log messages. Never log secrets, keys, or tokens.

```python
# ✅ CORRECT: Module-level logger with context
logger = logging.getLogger(__name__)

async def process_case(case_id: str) -> None:
    start = time.perf_counter()
    logger.info("Processing case %s", case_id)
    # ... work ...
    elapsed = time.perf_counter() - start
    logger.info("Case %s completed in %.2fs", case_id, elapsed)

# ❌ WRONG: Logging sensitive data
logger.info(f"Connecting with key={cosmos_key}")  # NEVER log secrets
```

## Summary

| Rule | Rationale |
|------|-----------|
| Thin route handlers | Separation of concerns; testability |
| Dependency injection | Loose coupling; easy testing with mocks |
| Explicit timeouts | Prevent indefinite hangs |
| Retry with backoff | Resilience against transient failures |
| Singleton CosmosClient | Avoid connection overhead and resource leaks |
| Structured logging | Debuggability without exposing secrets |
