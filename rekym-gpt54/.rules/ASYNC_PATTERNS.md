# Async Patterns

## Rules

1. Use `async def` for routes, repositories, services, and any I/O helper.
2. Use `aiohttp` for outbound HTTP calls.
3. Use `asyncio.gather()` for independent parallel work.
4. If `return_exceptions=True` is used, process results with explicit type guards.
5. Do not substitute normal async orchestration with thread pools.

## Required patterns

- Explicit timeouts for outbound I/O.
- Retry-aware handling for transient failures.
- Repository methods remain async end-to-end.
- Cosmos client operations use the async SDK.

## Example

```python
results = await asyncio.gather(*tasks, return_exceptions=True)

for result in results:
    if isinstance(result, Exception):
        logger.warning("Parallel task failed", extra={"error": str(result)})
        continue
    handle_success(result)
```