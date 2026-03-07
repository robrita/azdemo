# API Response Standards

## FastAPI Response Patterns

This project uses FastAPI with Pydantic schemas for request/response validation. Routes return typed dicts or Pydantic models — FastAPI handles JSON serialization.

## Success Response Structure

Endpoints return domain data directly (FastAPI auto-serializes):

```python
# List endpoint — returns list of dicts
@router.get("")
async def list_cases(...) -> list[dict[str, Any]]:
    return await case_repo.list_filtered(state=state)

# Detail endpoint — returns single dict
@router.get("/{case_id}")
async def get_case(...) -> dict[str, Any]:
    return case

# Create endpoint — returns created resource
@router.post("/trigger", status_code=201)
async def trigger_case(...) -> dict[str, Any]:
    return result
```

## Error Response Structure

Errors are handled via custom exception classes and global handlers in `backend/src/exceptions.py`:

```python
{
    "detail": "Descriptive error message"   # Actionable explanation
}
```

## HTTP Status Codes

| Code | Usage |
|------|-------|
| `200` | Successful read/update |
| `201` | Resource created |
| `400` | Validation errors, missing required fields |
| `401` | Missing authentication |
| `403` | Forbidden — tenant isolation or policy violation |
| `404` | Resource not found |
| `409` | Conflict — duplicate case, policy violation |
| `422` | Invalid state transition |
| `429` | Rate limit exceeded (includes `Retry-After` header) |
| `502` | External service failure (Partner DB, Google Drive) |

## Exception Classes

Use the typed exception hierarchy in `backend/src/exceptions.py`:

| Exception | Status | Usage |
|-----------|--------|-------|
| `NotFoundError` | 404 | Resource not found |
| `ConflictError` | 409 | Duplicate or conflict |
| `ForbiddenError` | 403 | Access denied by policy |
| `PolicyViolationError` | 409 | Self-approval, invalid workflow action |
| `InvalidTransitionError` | 422 | Invalid state machine transition |
| `RateLimitExceededError` | 429 | Rate limit hit |
| `ExternalServiceError` | 502 | Partner DB or Google Drive failure |

## Rules

1. **Use Pydantic schemas** for request validation — define in `backend/src/schemas/`
2. **Raise typed exceptions** — never return raw `JSONResponse` for errors in route handlers
3. **Keep routes thin** — delegate to service layer, return data
4. **Actionable error messages** — tell users what went wrong and how to fix it
5. **Include auth dependency** — all routes (except `/health`) require `get_current_user`
6. **Enforce tenant isolation** — use `TenantScopeGuard` for merchant-scoped endpoints
