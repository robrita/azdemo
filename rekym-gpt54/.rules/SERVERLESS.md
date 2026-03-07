# Serverless And Container Hosting

## Mandatory hosting modes

This template must preserve all of the following:

1. Azure Functions v2 hosting via `AsgiFunctionApp`.
2. Container hosting via `uvicorn`.
3. Shared business logic in `backend/src/`.

## Thin adapter rule

`function_app.py` is only a hosting adapter.

- It may set up Python import paths.
- It may import the FastAPI app.
- It must not contain business rules, data access, orchestration, or configuration branching.

## Azure Functions config

- Keep `host.json` in the project root.
- Keep `requirements.txt` in the project root for Functions packaging.
- Keep `local.settings.example.json` aligned with `.env.example`.