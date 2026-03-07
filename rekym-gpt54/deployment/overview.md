# Deployment Overview

This template preserves two mandatory backend hosting modes.

## Azure Functions

- `function_app.py` exposes the FastAPI app through `AsgiFunctionApp`.
- `host.json` configures the Functions host.
- `requirements.txt` contains the runtime packages required by the Functions worker.
- `local.settings.example.json` mirrors the backend configuration model.

## Containers

- `backend/Dockerfile` runs the FastAPI app with `uvicorn`.
- `frontend/Dockerfile` runs the Vite app in a container-friendly way.
- `docker-compose.yaml` brings up backend, frontend, and Cosmos emulator.

## Data store

Azure Cosmos DB remains the default data store in every deployment mode.