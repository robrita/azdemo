# Async & Parallel Execution Standards

## Core Rules

1. **Use `aiohttp`** instead of `requests` for HTTP calls — true async I/O without blocking the event loop
2. **Use `asyncio.gather()`** instead of `ThreadPoolExecutor` — true parallel I/O, lower overhead
3. **Declare `async def`** for all route handlers and helper functions that perform I/O
4. **Use proper type guards** when processing `asyncio.gather()` results with `return_exceptions=True`

## Pattern: Async HTTP Requests

```python
import aiohttp

async def _call_external_api(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Make async HTTP request to external service."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response,
    ):
        response.raise_for_status()
        return await response.json()
```

## Pattern: Parallel Execution with Gather

```python
result, _ = await asyncio.gather(
    item_repo.create(item_doc),
    audit_writer.write_event(event_doc),
)
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

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| `requests.get(url)` | `aiohttp.ClientSession().get(url)` |
| `ThreadPoolExecutor` for I/O | `asyncio.gather()` |
| `def handler()` for I/O routes | `async def handler()` |
| Bare `asyncio.gather()` results | Type-guard with `isinstance(result, Exception)` |
