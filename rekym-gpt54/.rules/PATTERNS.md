# Reuse Patterns

## Rules

1. Check for an existing helper before introducing a new one.
2. Keep DI providers centralized in `backend/src/dependencies.py`.
3. Keep shared frontend styling in `frontend/src/index.css` and `frontend/src/theme/tokens.ts`.
4. Keep repositories as the only layer that issues Cosmos queries.
5. Remove deprecated settings, code paths, docs, and env vars completely.

## Backend patterns

- Models define serialized aliases.
- Schemas define HTTP contracts.
- Services orchestrate business logic.
- Repositories encapsulate data access.

## Frontend patterns

- Feature modules own page-specific UI.
- Shared components stay generic.
- API clients stay centralized.