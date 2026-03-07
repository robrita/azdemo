# Template Agent Guide

Portable full-stack starter for FastAPI + React + Vite + Azure Functions + Azure Cosmos DB.

## Core Rules

1. Async-first backend code only. Use `async def`, `aiohttp`, and `asyncio.gather()` for I/O orchestration.
2. Keep the backend layered: route -> service -> repository -> Cosmos client.
3. Use Azure Cosmos DB as the default primary store. Do not replace it with an in-memory or local SQL default.
4. Keep `function_app.py` as a thin ASGI host adapter. Business logic lives in `backend/src/`.
5. Backend config must come only from `backend/src/config.py` via `Settings(BaseSettings)`.
6. Keep config parity across `.env.example`, `.env`, `local.settings.example.json`, Docker Compose, and settings fields.
7. Exact-pin Python dependencies with `==`.
8. Use camelCase document fields in Cosmos DB and escape reserved query fields with `c["field"]`.
9. Reuse helpers and DI providers before adding new abstractions.
10. Frontend styles must use centralized semantic tokens and shared component classes.
11. Every frontend change must work in both light and dark mode.
12. Root `make` targets are the primary developer workflow.
13. Docker Compose is the default full-stack local runtime.
14. Health probes must remain explicit: `/health`, `/health/live`, `/health/ready`.
15. Logging must stay structured and correlation-aware.

## Reading Order

1. This file.
2. `.rules/ARCHITECTURE.md`.
3. `.rules/RUNTIME.md`.
4. `.rules/CONFIG_MANAGEMENT.md`.
5. `.rules/COSMOS_FIELD_NAMING.md`.
6. `.rules/QUALITY_GATES.md`.
7. The relevant domain guide under `backend/`, `frontend/`, `deployment/`, `tooling/`, or `verification/`.

## Expected Stack

- Python 3.12+
- FastAPI
- Azure Functions v2 `AsgiFunctionApp`
- Azure Cosmos DB async SDK
- React
- TypeScript
- Vite
- Tailwind CSS
- Docker Compose

## Delivery Standard

When updating this template, keep documentation and starter assets in sync. Do not update the contract without updating the starter code, and do not change the starter code without updating the template docs.