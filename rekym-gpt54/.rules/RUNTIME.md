# Runtime

## Local development

The backend must run from the repository root.

- `make dev` starts FastAPI from the root directory.
- `make frontend-dev` starts the Vite dev server from the root directory.
- Root `.env.example` and `.env` are the backend configuration source for local dev.

## Docker Compose

Docker Compose is the default full-stack local runtime.

- Backend runs the same FastAPI app through `uvicorn`.
- Frontend runs the Vite dev server.
- Cosmos DB defaults to a local emulator container.
- Compose reads the root `.env` file and may override only container-network-specific values.

## Observability baseline

- Structured JSON logging.
- Correlation ID propagation.
- Request and exception logging.
- `/health`, `/health/live`, `/health/ready`.
- Frontend error telemetry intake endpoint.

## Reliability rules

- Use explicit timeouts for outbound calls.
- Retry transient failures, especially Cosmos `429` responses.
- Keep request handling stateless.
- Reuse singleton clients instead of creating per-request clients.