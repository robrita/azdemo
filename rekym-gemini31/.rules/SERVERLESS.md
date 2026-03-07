# Containerized Runtime

## Docker Compose Deployment

This project runs as a containerized stack via Docker Compose. The production-like environment includes:

- **FastAPI backend** — `backend/Dockerfile`, port 8000
- **React frontend** — `frontend/Dockerfile`, port 5173

### Rules

1. **All services must be defined in `docker-compose.yaml`** — never run services outside the compose stack in production
2. **Use volume mounts for hot-reload** — `backend/src` and `frontend/src` are mounted for development
3. **Environment variables via `.env` files** — backend reads from `backend/.env`
4. **Stateless request handling** — do not store state in the FastAPI process; use Cosmos DB
5. **Health checks** — backend exposes `/health` endpoint for container orchestration

### Local Development

Alternative to Docker Compose for faster iteration:

```bash
# Backend (from project root)
make dev              # uvicorn with auto-reload on port 8000

# Frontend (from project root)
make frontend-dev     # vite dev server on port 5173
```

## Cross-Platform Compatibility

All code and scripts must work on both Windows and Linux:

1. Use `pathlib.Path` (or equivalent cross-platform APIs) for file/path operations
2. Avoid shell-specific assumptions in scripts and commands
3. Keep line endings and path separators platform-agnostic
4. Validate that local development commands are reproducible across environments
