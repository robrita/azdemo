# Backend Overview

The backend starter demonstrates the required repository standard in a minimal domain.

## Included behaviors

- FastAPI app with lifespan-managed Cosmos client.
- Root-loaded typed config via `Settings(BaseSettings)`.
- Structured JSON logging and correlation ID propagation.
- Thin routes backed by services and repositories.
- Async Cosmos SDK usage.
- Explicit health probes.
- Typed exceptions and centralized handlers.
- Sample telemetry intake endpoint.

## Domain sample

The starter uses a `merchants` domain because it is simple enough to understand quickly while still exercising the required layers and Cosmos rules.

## Extension guidance

- Add new domains by creating models, schemas, repositories, services, routes, and DI providers.
- Do not skip from routes directly to Cosmos.
- Keep Cosmos query text parameterized and alias-aware.