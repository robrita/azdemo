# Cosmos DB Rules

Azure Cosmos DB is mandatory in this template.

## Document naming

- Store document fields in camelCase.
- Match query paths to serialized aliases, not Python snake_case names.
- Keep partition keys explicit and intentional.

## Query rules

- Parameterize queries.
- Escape reserved words with `c["field"]`.
- Do not use `c.[field]`.

## Client and retry rules

- Use one async Cosmos client per process.
- Reuse the database and container clients.
- Handle `429` responses with retry-after backoff.
- Capture diagnostics when latency or status codes are suspicious.

## Indexing and singleton rules

- Do not include `/id/?` in custom `includedPaths`.
- Use singleton IDs in the form `{type}:{key}`.
- Keep indexing policy paths aligned to camelCase serialized field names.

## Starter container conventions

- `merchants` partition key: `/tenantId`
- `auditEvents` partition key: `/tenantId`

These starter containers are intentionally simple but preserve the rules needed for real domains.