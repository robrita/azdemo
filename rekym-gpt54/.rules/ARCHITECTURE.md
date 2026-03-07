# Architecture

## Application Shape

The backend uses a fixed layered architecture:

`Request -> Route -> Service -> Repository -> Cosmos DB`

### Layer responsibilities

- `backend/src/routes/`: HTTP boundary, request parsing, response typing, dependency wiring.
- `backend/src/schemas/`: Pydantic request and response DTOs.
- `backend/src/services/`: Business logic and orchestration.
- `backend/src/repositories/`: Cosmos DB access, queries, pagination, retries.
- `backend/src/models/`: Domain entities with camelCase aliases.
- `backend/src/cosmos/`: Singleton client, database bootstrap, container access.
- `backend/src/lib/`: Shared observability and utility helpers.
- `backend/src/middleware/`: Auth and request-scoped behaviors.

## Backend runtime boundaries

- `backend/src/main.py` creates the FastAPI app.
- `function_app.py` imports the FastAPI app and exposes it through `func.AsgiFunctionApp`.
- Container deployment runs the same app through `uvicorn`.
- All long-lived clients are created in lifespan-managed objects and reused.

## Frontend architecture

- `frontend/src/app/`: app shell, providers, route registration.
- `frontend/src/features/`: feature-oriented UI modules.
- `frontend/src/components/`: shared presentational components.
- `frontend/src/services/`: API and telemetry clients.
- `frontend/src/theme/`: semantic theme tokens.

## Storage contract

Azure Cosmos DB is mandatory in this template.

- Use one singleton Cosmos client per process.
- Model documents around partition-aware access patterns.
- Use camelCase serialized field names.
- Keep document and response models explicit and typed.
- Hide all Cosmos queries behind repositories.

## Sample domain

The starter domain uses a simple `merchants` flow to demonstrate the architecture without hard-coding a product-specific workflow.

- `POST /api/v1/merchants`
- `GET /api/v1/merchants`
- `GET /api/v1/merchants/{merchantId}`
- `POST /api/v1/telemetry/frontend-errors`
- `/health`, `/health/live`, `/health/ready`