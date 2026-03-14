# Cosmos DB Conventions

## Field Naming: camelCase

All document fields stored in Cosmos DB use **camelCase**. Pydantic models serialize with camelCase aliases (Python `item_name` → Cosmos DB `itemName`).

Indexing policies, excluded paths, and composite indexes must use the exact camelCase field names.

## Pydantic Model Convention

```python
class ItemModel(BaseModel):
    item_id: str = Field(alias="itemId")
    created_at: str = Field(alias="createdAt")
    model_config = {"populate_by_name": True}
```

## Reserved Word Escaping

Some field names (`key`, `value`, `type`, `status`) are reserved words in Cosmos DB SQL.

| Syntax | Result |
|--------|--------|
| `c["key"]` | **Correct** |
| `c.[key]` | **BadRequest — invalid** |
| `c.key` | Unreliable with reserved words |

## Indexing Policy: No `/id/?`

Never add `/id/?` to `includedPaths`. Cosmos DB treats `id` as a system property — explicitly indexing it causes `BadRequest`.

## Singleton Document IDs

Singleton/config documents must use collision-safe IDs: `"{type}:{key}"` (e.g., `"config:rate-limits"`). Never use `"default"`.

## Parameterized Queries

Always use parameterized queries. Never interpolate values into query strings.

```python
# ✅ Correct
query = "SELECT * FROM c WHERE c.itemId = @itemId"
params = [{"name": "@itemId", "value": item_id}]

# ❌ Wrong — SQL injection risk
query = f"SELECT * FROM c WHERE c.itemId = '{item_id}'"
```

## Client Management

- Use the `CosmosClientManager` singleton via FastAPI lifespan
- Never create clients per request
- Use async SDK (`azure.cosmos.aio`)
- Handle 429 (rate limit) with retry and backoff

## Pydantic → Cosmos Serialization: Use `mode="json"`

When dumping a Pydantic model to a dict for Cosmos DB, always use `mode="json"` so that `datetime` (and other non-primitive types) are serialized to JSON-safe values (ISO 8601 strings). Without it, `datetime` objects reach the Cosmos SDK's `json.dumps` and raise `TypeError: Object of type datetime is not JSON serializable`.

```python
# ✅ Correct
doc = model.model_dump(by_alias=True, mode="json")

# ❌ Wrong — datetime fields remain native Python objects
doc = model.model_dump(by_alias=True)
```

## Repository Pattern

All repositories extend `BaseRepository` which provides:
- `create(item)`, `read(item_id, partition_key)`, `upsert(item)`, `delete(item_id, partition_key)`
- `query(query_text, parameters, partition_key)`, `count(query_text, parameters, partition_key)`

## Partition Key Guidance

- Choose a partition key with high cardinality and even distribution
- Always supply partition key in point reads for efficiency
- Cross-partition queries are expensive — design data model to avoid them
