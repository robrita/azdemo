# API Response Standards

## Success Responses

Endpoints return domain data directly (FastAPI auto-serializes):

```python
@router.get("")
async def list_items(...) -> list[dict[str, Any]]:
    return await item_repo.list_all()

@router.get("/{item_id}")
async def get_item(...) -> dict[str, Any]:
    return item

@router.post("", status_code=201)
async def create_item(...) -> dict[str, Any]:
    return result
```

## Error Response Structure

```json
{ "detail": "Descriptive, actionable error message" }
```

## HTTP Status Codes

| Code | Usage |
|------|-------|
| `200` | Successful read/update |
| `201` | Resource created |
| `400` | Validation errors, missing fields |
| `401` | Missing authentication |
| `403` | Forbidden — access policy violation |
| `404` | Resource not found |
| `409` | Conflict — duplicate or policy violation |
| `422` | Invalid state transition |
| `429` | Rate limit exceeded (include `Retry-After` header) |
| `502` | External service failure |

## Exception Classes

Use the typed exception hierarchy in `backend/src/exceptions.py`:

| Exception | Status | Usage |
|-----------|--------|-------|
| `NotFoundError` | 404 | Resource not found |
| `ConflictError` | 409 | Duplicate or conflict |
| `ForbiddenError` | 403 | Access denied by policy |
| `ExternalServiceError` | 502 | External service failure |

## Rules

1. **Use Pydantic schemas** for request validation — define in `backend/src/schemas/`
2. **Raise typed exceptions** — never return raw `JSONResponse` for errors
3. **Keep routes thin** — delegate to service layer, return data
4. **Actionable error messages** — tell users what went wrong and how to fix it
5. **Explicit timeouts** on all external calls
