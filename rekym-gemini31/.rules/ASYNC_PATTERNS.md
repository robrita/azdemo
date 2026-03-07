# Async & Parallel Execution Standards

## Core Rules

1. **Use `aiohttp`** instead of `requests` for HTTP calls — true async I/O without blocking the event loop
2. **Use `asyncio.gather()`** instead of `ThreadPoolExecutor` — true parallel I/O, lower overhead, better error handling
3. **Declare `async def`** for all route handlers and helper functions that perform I/O
4. **Use proper type guards** when processing `asyncio.gather()` results with `return_exceptions=True`

## Pattern: Async HTTP Requests

```python
import aiohttp

async def _call_partner_db(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Make async HTTP request to Partner DB."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response,
    ):
        response.raise_for_status()
        return await response.json()
```

## Pattern: Parallel Execution with Gather

```python
@router.post("/trigger", status_code=201)
async def trigger_case(
    body: TriggerRequest,
    user: AuthUser = Depends(get_current_user),
    case_repo: CaseRepository = Depends(get_case_repo),
    audit_writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    # Execute independent operations in parallel
    result, _ = await asyncio.gather(
        case_repo.create(case_doc),
        audit_writer.write_state_transition(
            case_id=case_id,
            actor_id=user.user_id,
            actor_type="user",
            from_state="",
            to_state=CaseState.DUE,
            reason="Case triggered",
        ),
    )
    return result
```

## Pattern: Gather with Exception Handling

```python
tasks = [process_item(item) for item in items]
results = await asyncio.gather(*tasks, return_exceptions=True)

for result in results:
    if isinstance(result, Exception):
        logger.error("Operation failed: %s", str(result))
        continue
    # Process successful result
```

## Why These Patterns

| Approach | Benefit |
|----------|---------|
| `aiohttp` over `requests` | Non-blocking I/O, native async/await |
| `asyncio.gather()` over `ThreadPoolExecutor` | No GIL blocking, lower memory overhead |
| `async def` handlers | End-to-end non-blocking pipeline |
| Type guards on results | Safe handling of mixed success/exception results |
