# Code Patterns & Reusability

## Before Implementing Anything

1. Check if similar logic exists elsewhere in the codebase
2. Create reusable helper functions instead of duplicating code
3. Extract common patterns into shared utilities

## Dependency Injection Pattern

All dependencies are wired via `backend/src/dependencies.py`. Use FastAPI's `Depends()`:

```python
from src.dependencies import get_item_repo

@router.get("/{item_id}")
async def get_item(
    item_id: str,
    item_repo: ItemRepository = Depends(get_item_repo),
) -> dict[str, Any]:
    return await item_repo.read(item_id)
```

## Repository Pattern

All repositories extend `BaseRepository` in `backend/src/repositories/base.py`.

Domain-specific repositories add their own methods:

```python
class ItemRepository(BaseRepository):
    def __init__(self, database: DatabaseProxy) -> None:
        super().__init__(database, "items")

    async def find_by_status(self, status: str) -> list[dict[str, Any]]:
        return await self.query(
            "SELECT * FROM c WHERE c.status = @status",
            [{"name": "@status", "value": status}],
        )
```

## Typed Exception Pattern

Use the exception hierarchy in `backend/src/exceptions.py`:

```python
from src.exceptions import NotFoundError, ConflictError

raise NotFoundError(f"Item {item_id} not found")
raise ConflictError(f"Item already exists")
```

Never return raw `JSONResponse` for errors in route handlers.

## Pydantic Model Convention

- **Models** (`backend/src/models/`) — domain entities with camelCase aliases
- **Schemas** (`backend/src/schemas/`) — request/response DTOs

```python
class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(alias="category")
    model_config = {"populate_by_name": True}
```

## Parallel Execution Pattern

Use `asyncio.gather()` for independent async operations:

```python
result, _ = await asyncio.gather(
    item_repo.create(item_doc),
    audit_writer.write_event(event_doc),
)
```
