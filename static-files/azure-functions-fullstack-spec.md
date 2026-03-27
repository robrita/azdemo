# Azure Functions Full-Stack Deployment Spec

> **Purpose**: Reusable template reference for hosting a FastAPI + React SPA on
> Azure Functions v2 (Python) via the ASGI adapter. Copy relevant sections when
> bootstrapping a new project.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Azure Function App  (Linux, Python 3.12, Consumption/Flex)     │
│                                                                 │
│  function_app.py          ← ASGI adapter (thin hosting layer)   │
│    └─ FastAPI app         ← backend/src/main.py                 │
│         ├─ /health        ← API routes (registered first)       │
│         ├─ /extract       ← API routes                          │
│         ├─ /docs          ← Swagger UI (auto-generated)         │
│         └─ /  (mount)     ← StaticFiles(html=True) catch-all    │
│              └─ frontend/dist/  ← React SPA build output        │
└─────────────────────────────────────────────────────────────────┘
```

**Key design decisions**:

- **Single deployment unit**: backend + frontend ship together. No separate
  Static Web App or CDN required.
- **ASGI adapter**: `azure.functions.AsgiFunctionApp` wraps the FastAPI app.
  Azure Functions handles HTTP routing, scaling, and cold starts.
- **Empty route prefix**: `host.json` sets `"routePrefix": ""` so all routes
  are served at root (no `/api/` prefix).
- **SPA catch-all last**: `StaticFiles(directory=..., html=True)` is mounted
  at `/` **after** all API routers. Unknown paths serve `index.html` for
  client-side routing. API routes always take priority.

---

## 2. Project Structure (Deployment-Relevant Files)

```
<project-root>/
├── function_app.py             # Azure Functions entrypoint (ASGI adapter)
├── host.json                   # Azure Functions host config
├── requirements.txt            # Python deps (Azure reads this)
├── .funcignore                 # Excludes non-runtime files from deploy zip
├── local.settings.json         # Local dev config (NOT deployed)
├── local.settings.example.json # Template for local.settings.json
├── local.env.json              # Azure app settings mirror (for az CLI sync)
│
├── backend/
│   └── src/
│       ├── main.py             # FastAPI app factory (create_app)
│       ├── config.py           # Settings(BaseSettings) — centralized config
│       ├── routes/             # API route modules
│       └── ...
│
└── frontend/
    ├── package.json            # "build": "tsc -b && vite build"
    ├── vite.config.ts          # Vite config (dev proxy, plugins)
    └── dist/                   # Build output (generated, gitignored)
```

---

## 3. File-by-File Specification

### 3.1 `function_app.py` — ASGI Hosting Adapter

```python
"""Azure Functions v2 entrypoint — hosts the FastAPI app via ASGI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import azure.functions as func

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Resolve relative STATIC_DIR against project root so the path works
# regardless of the working directory Azure Functions uses at runtime.
_static = os.environ.get("STATIC_DIR", "")
if _static and not Path(_static).is_absolute():
    os.environ["STATIC_DIR"] = str(PROJECT_ROOT / _static)

from src.main import app as fastapi_app  # noqa: E402

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
```

**Why this matters**:

| Concern | Solution |
|---------|----------|
| `sys.path` | Backend code lives in `backend/src/`, not at project root. Must add `backend/` to path before importing. |
| `STATIC_DIR` path resolution | Azure Functions' CWD may not be `/home/site/wwwroot/`. Relative paths like `frontend/dist` must be resolved against `PROJECT_ROOT` to become absolute. Without this, `Path("frontend/dist").is_dir()` returns `False` and static serving silently fails. |
| `http_auth_level` | Set to `ANONYMOUS` — auth is handled by FastAPI middleware, not Azure Functions. |

### 3.2 `host.json` — Azure Functions Host Configuration

```json
{
  "version": "2.0",
  "extensions": {
    "http": {
      "routePrefix": ""
    }
  },
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "excludedTypes": "Request"
      },
      "enableDependencyTracking": false
    },
    "logLevel": {
      "default": "Warning",
      "Function": "Information",
      "azure.core.pipeline.policies.http_logging_policy": "Warning",
      "azure": "Warning"
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

**Critical setting**: `"routePrefix": ""` removes the default `/api/` prefix.
Without this, all routes would require `/api/health`, `/api/extract`, etc.

### 3.3 `backend/src/main.py` — Static File Mount (Relevant Section)

```python
def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="My App API", version="0.1.0", lifespan=lifespan)

    # ... middleware, CORS, exception handlers ...

    # Routers — registered BEFORE static mount
    application.include_router(health.router, tags=["Health"])
    application.include_router(extract.router)

    # Serve frontend static build (must be last — catch-all mount)
    static_dir = Path(settings.static_dir) if settings.static_dir else None
    if static_dir and static_dir.is_dir():
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        logger.info("Serving frontend static files from %s", static_dir)
    elif settings.static_dir:
        logger.warning(
            "STATIC_DIR=%r is set but path does not exist or is not a directory "
            "(resolved: %s, exists: %s, is_dir: %s)",
            settings.static_dir,
            static_dir,
            static_dir.exists() if static_dir else False,
            static_dir.is_dir() if static_dir else False,
        )
    else:
        logger.info("STATIC_DIR is empty — frontend static file serving disabled")

    return application
```

**Registration order is critical**:

1. API routers registered first → `/health`, `/extract`, `/docs` match before static
2. `StaticFiles` mounted last at `/` → catches everything else
3. `html=True` enables SPA fallback: any 404 within the mount serves `index.html`

### 3.4 `backend/src/config.py` — `STATIC_DIR` Setting

```python
class Settings(BaseSettings):
    # ...
    static_dir: str = Field(
        default="",
        description="Path to frontend static build directory (empty = disabled)",
    )
```

- Default is `""` (disabled) — static serving is opt-in
- Set via `STATIC_DIR` environment variable
- When empty, the app serves only API routes (no frontend)

### 3.5 `.funcignore` — Deployment Package Control

Controls what the `func azure functionapp publish` command includes:

```
# Included (NOT listed in .funcignore):
#   function_app.py           ← ASGI entrypoint
#   host.json                 ← host config
#   requirements.txt          ← Python deps
#   backend/src/              ← application code
#   frontend/dist/            ← built SPA assets ← CRITICAL

# Excluded:
frontend/node_modules/        # Dev deps — not needed at runtime
frontend/src/                 # Source — only dist/ is needed
frontend/package.json         # Build config — not needed at runtime
backend/tests/                # Tests — not needed at runtime
.venv/                        # Local venv
local.settings.json           # Secrets — configured via Azure App Settings
pyproject.toml                # Build metadata
# ...
```

**The most important inclusion**: `frontend/dist/` must NOT appear in
`.funcignore`. This directory contains the built SPA and must ship with the
deployment package.

### 3.6 `requirements.txt` — Azure Functions Dependency File

Azure Functions reads `requirements.txt` (not `pyproject.toml`) for Python
dependency installation. Keep this in sync with `pyproject.toml` dependencies:

```
aiohttp==3.13.3
azure-functions==1.24.0
fastapi==0.129.2
pydantic==2.12.5
pydantic-settings==2.13.1
uvicorn[standard]==0.41.0
# ... other project-specific deps
```

**Must include**: `azure-functions` — the ASGI adapter runtime.

---

## 4. Configuration Management

### 4.1 Environment Variable Flow

```
┌─────────────────────┐    ┌──────────────────────────┐
│ local.settings.json │    │ Azure App Settings       │
│ (local dev only)    │    │ (Portal / az CLI)        │
└────────┬────────────┘    └────────────┬─────────────┘
         │                              │
         ▼                              ▼
┌─────────────────────────────────────────────────────┐
│           os.environ (process environment)           │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│     function_app.py — resolves STATIC_DIR path       │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│     Settings(BaseSettings) — typed config object     │
│     Loaded via get_settings() singleton              │
└─────────────────────────────────────────────────────┘
```

### 4.2 Required Azure App Settings

These must be set on the Azure Function App (via Portal or CLI). They are
**not** deployed from `local.settings.json`.

| Setting | Example Value | Purpose |
|---------|---------------|---------|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Required by Azure Functions |
| `AzureWebJobsStorage` | `DefaultEndpointsProtocol=https;...` | Functions internal storage |
| `AzureWebJobsFeatureFlags` | `EnableWorkerIndexing` | Required for v2 Python model |
| `STATIC_DIR` | `frontend/dist` | Path to SPA build output (relative to project root) |
| `CORS_ORIGINS` | `["https://myapp.azurewebsites.net"]` | Allowed CORS origins (JSON array as string) |
| `AUTH_MODE` | `header` or `disabled` | API authentication mode |
| `API_KEY` | `<secret>` | API key (required when `AUTH_MODE=header`) |
| `APP_ENV` | `development` / `production` | Environment identifier |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_JSON` | `true` | Structured JSON logging |
| `APPLICATION_INSIGHTS_CONNECTION_STRING` | `InstrumentationKey=...` | App Insights telemetry |

**Set via CLI**:
```bash
az functionapp config appsettings set \
  --name <app-name> \
  --resource-group <rg-name> \
  --settings \
    "STATIC_DIR=frontend/dist" \
    "AUTH_MODE=header" \
    "API_KEY=<your-key>" \
    "CORS_ORIGINS=[\"https://<app-name>.azurewebsites.net\"]"
```

### 4.3 Config Parity Checklist

When adding/changing an env var, update ALL of these:

| File | Format | Purpose |
|------|--------|---------|
| `backend/src/config.py` | Python `Field(...)` | Typed config definition |
| `local.settings.example.json` | `"KEY": "value"` in `Values` | Template for local dev |
| `local.settings.json` | Same as example | Local dev (gitignored) |
| `local.env.json` | `[{"name":"KEY","value":"..."}]` | Azure app settings mirror |
| `docker-compose.yaml` | `environment:` section | Docker dev |
| `.env.example` | `KEY=value` | Docker env file template |

---

## 5. Deployment

### 5.1 Deploy Command

```bash
# 1. Build frontend
cd frontend && npm run build

# 2. Publish to Azure Functions
func azure functionapp publish <app-name> --python --build remote
```

Or via Makefile:
```bash
make deploy   # Runs frontend-build then publishes
```

**`--build remote`**: Azure's Oryx build system installs Python dependencies
from `requirements.txt` on the server. The `frontend/dist/` directory is
included as a pre-built artifact (not built on Azure).

### 5.2 What Gets Deployed

The `func` CLI creates a zip of the project, excluding paths in `.funcignore`:

```
<deploy-zip>/
├── function_app.py
├── host.json
├── requirements.txt
├── backend/
│   └── src/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── routes/
│       ├── services/
│       ├── schemas/
│       └── lib/
└── frontend/
    └── dist/
        ├── index.html
        ├── assets/
        │   ├── index-<hash>.js
        │   └── index-<hash>.css
        └── favicon.svg
```

### 5.3 Azure Runtime File Layout

On Azure, files are extracted to:

```
/home/site/wwwroot/
├── function_app.py
├── host.json
├── requirements.txt
├── backend/src/...
├── frontend/dist/...
└── .python_packages/          ← installed by Oryx from requirements.txt
```

`function_app.py` resolves `STATIC_DIR=frontend/dist` to
`/home/site/wwwroot/frontend/dist` at startup, ensuring the static mount
works regardless of the Azure Functions worker's CWD.

---

## 6. Docker (Alternative Deployment)

### 6.1 Multi-Stage Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM node:18-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Backend + built frontend
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable
COPY backend/src/ src/
COPY --from=frontend-builder /app/dist ./static
ENV STATIC_DIR=/app/static
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 Docker Compose (Local Development)

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./.env
    environment:
      - STATIC_DIR=/app/static
    volumes:
      - ./backend/src:/app/src        # Hot-reload backend
      - ./frontend/dist:/app/static:ro # Mount built frontend

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
    volumes:
      - ./frontend/src:/app/src        # Hot-reload frontend
```

---

## 7. Request Routing Table

| Request Path | Matched By | Response |
|-------------|------------|----------|
| `GET /health` | `health.router` | `{"status": "ok"}` |
| `GET /health/live` | `health.router` | `{"status": "ok"}` |
| `GET /health/ready` | `health.router` | `{"status": "ok"}` |
| `POST /extract` | `extract.router` | Extraction result JSON |
| `GET /docs` | FastAPI auto-generated | Swagger UI |
| `GET /openapi.json` | FastAPI auto-generated | OpenAPI schema |
| `GET /` | `StaticFiles` mount | `index.html` |
| `GET /assets/main-abc.js` | `StaticFiles` mount | JS bundle |
| `GET /any/spa/route` | `StaticFiles` SPA fallback | `index.html` |

**Priority**: FastAPI routers are checked first (registered before the mount).
The `StaticFiles` catch-all only handles requests that don't match any router.

---

## 8. Troubleshooting

### Problem: `{"detail": "Not Found"}` on root `/`

**Cause**: `StaticFiles` mount was skipped at startup. Check in order:

1. **`STATIC_DIR` not set in Azure App Settings**
   - `local.settings.json` is NOT deployed. The setting must exist in Azure.
   - Fix: `az functionapp config appsettings set --name <app> --resource-group <rg> --settings "STATIC_DIR=frontend/dist"`

2. **`frontend/dist/` missing from deployment package**
   - Run `make frontend-build` (or `cd frontend && npm run build`) before deploying.
   - Verify `.funcignore` does NOT exclude `frontend/dist/`.

3. **Relative path not resolved**
   - If `function_app.py` doesn't resolve `STATIC_DIR` to an absolute path,
     `Path("frontend/dist").is_dir()` may return `False` when the CWD differs
     from the project root.
   - Fix: Add the `PROJECT_ROOT / _static` resolution in `function_app.py`
     (see Section 3.1).

4. **Check logs** — Look for these messages in the Azure log stream:
   - `"Serving frontend static files from ..."` → success
   - `"STATIC_DIR=... is set but path does not exist"` → path issue
   - `"STATIC_DIR is empty"` → missing app setting

### Problem: API routes return 404 but static files work

**Cause**: `StaticFiles` mount registered before API routers (catches all requests).
**Fix**: Ensure `application.mount("/", StaticFiles(...))` is the LAST registration
in `create_app()`, after all `include_router()` calls.

### Problem: SPA routes return 404 (e.g., `/dashboard`)

**Cause**: `html=True` not set on `StaticFiles`.
**Fix**: `StaticFiles(directory=..., html=True)` — the `html=True` parameter
makes the mount serve `index.html` for any path that doesn't match a real file.

---

## 9. Checklist for New Projects

- [ ] Create `function_app.py` with ASGI adapter and `STATIC_DIR` path resolution
- [ ] Create `host.json` with `"routePrefix": ""`
- [ ] Create `requirements.txt` including `azure-functions` and `fastapi`
- [ ] Add `STATIC_DIR` field to `Settings(BaseSettings)` with empty default
- [ ] Mount `StaticFiles(html=True)` at `/` AFTER all API routers in `create_app()`
- [ ] Add diagnostic logging for skipped static mount (else/elif branches)
- [ ] Create `.funcignore` — exclude dev files, keep `frontend/dist/`
- [ ] Set `STATIC_DIR=frontend/dist` in Azure App Settings
- [ ] Run `npm run build` in frontend before deploying
- [ ] Deploy: `func azure functionapp publish <name> --python --build remote`
- [ ] Verify: `/` serves HTML, `/docs` serves Swagger, `/health` returns JSON
