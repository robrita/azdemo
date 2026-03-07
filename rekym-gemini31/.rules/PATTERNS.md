# Code Patterns & Reusability

## Before Implementing Anything

1. Check if similar logic exists elsewhere in the codebase
2. Create reusable helper functions instead of duplicating code across routes
3. Extract common patterns into shared utilities
4. When two functions are always called together, consider merging them

## Dependency Injection Pattern

All dependencies are wired via `backend/src/dependencies.py`. Use FastAPI's `Depends()`:

```python
from src.dependencies import get_case_repo, get_audit_writer, get_tenant_guard

@router.post("/trigger", status_code=201)
async def trigger_case(
    body: TriggerRequest,
    user: AuthUser = Depends(get_current_user),
    case_repo: CaseRepository = Depends(get_case_repo),
    audit_writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    ...
```

## Repository Pattern

All repositories extend `BaseRepository` in `backend/src/repositories/base.py` which provides:

- `create(item)` — create a new item
- `read(item_id, partition_key)` — read by ID + partition key
- `upsert(item)` — create or replace
- `delete(item_id, partition_key)` — delete by ID + partition key
- `query(query_text, parameters, partition_key)` — parameterized query
- `count(query_text, parameters, partition_key)` — scalar count

Domain-specific repositories add their own methods:

```python
class CaseRepository(BaseRepository):
    def __init__(self, database: DatabaseProxy) -> None:
        super().__init__(database, "cases")

    async def has_active_case(self, merchant_id: str, trigger_type: str) -> bool:
        ...
```

## Typed Exception Pattern

Use the exception hierarchy in `backend/src/exceptions.py` — never return raw JSON error responses from route handlers:

```python
from src.exceptions import NotFoundError, ConflictError, PolicyViolationError

# ✅ CORRECT: Raise typed exception
raise NotFoundError(f"Case {case_id} not found")
raise ConflictError(f"Active case already exists for merchant {merchant_id}")
raise PolicyViolationError("Maker cannot approve their own case")

# ❌ WRONG: Return raw JSONResponse
return JSONResponse(status_code=404, content={"detail": "Not found"})
```

## Tenant Isolation Pattern

Use `TenantScopeGuard` for all endpoints that access merchant-scoped data:

```python
tenant_guard.enforce(user, case["merchantId"])
```

For merchant users, auto-scope to their own `merchant_id`:

```python
if user.user_type == "merchant":
    effective_merchant_id = user.merchant_id
```

## Audit Trail Pattern

Every state transition must produce an audit event via `AuditWriter`:

```python
await audit_writer.write_state_transition(
    case_id=case_id,
    actor_id=user.user_id,
    actor_type="user",
    from_state=old_state,
    to_state=new_state,
    reason="Descriptive reason",
)
```

## Pydantic Model Convention

- **Models** (`backend/src/models/`) — domain entities with camelCase aliases, `populate_by_name=True`
- **Schemas** (`backend/src/schemas/`) — request/response DTOs for route handlers

```python
class TriggerRequest(BaseModel):
    merchant_id: str = Field(alias="merchantId")
    trigger_type: str = Field(alias="triggerType")
    model_config = {"populate_by_name": True}
```

## Parallel Execution Pattern

Use `asyncio.gather()` for independent async operations:

```python
result, _ = await asyncio.gather(
    case_repo.create(case_doc),
    audit_writer.write_state_transition(...),
)
```

## Feature Removal Workflow

When removing features or dependencies, follow this order:

1. **Dependencies** — remove from `pyproject.toml`
2. **Imports** — remove all import statements
3. **Configuration** — remove setup code, constants, environment variables
4. **Helper functions** — remove utility functions specific to the feature
5. **Usage** — find all calls with grep/search and remove
6. **Documentation** — update config templates and comments
7. **Verify** — grep for zero remaining references
8. **Lint** — ensure no errors introduced
