# Dependency Rules

## Python

1. Use exact `==` pins for every runtime and dev dependency.
2. Keep runtime and dev dependencies separated in `pyproject.toml`.
3. Keep `requirements.txt` aligned with runtime dependencies needed by Azure Functions.

## Frontend

1. Use explicit versions in `frontend/package.json`.
2. Keep installs reproducible.
3. Keep build, lint, test, and format scripts in `frontend/package.json`.

## Tooling

- Prefer `pip install -e ".[dev]"` for backend local dev.
- Use npm from `frontend/` for frontend dependency installation.