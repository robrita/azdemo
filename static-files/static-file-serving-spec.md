# Static File Serving via FastAPI StaticFiles Mount — Design Spec

> **Status:** Reverted (documented for reference)
> **Commit:** `d50ea58` — *feat: static file serving via StaticFiles mount, favicon cache buster, config parity*
> **Date:** 2026-03-16

## 1. Overview

This spec documents a pattern where the FastAPI backend serves the frontend SPA (React/Vite build output) directly using Starlette's `StaticFiles` middleware mounted at the root path (`/`). The intent was to replace a manual SPA catch-all route with a cleaner, framework-native approach.

**This pattern was reverted** in favor of the original manual SPA catch-all. This document captures what was implemented, why, and the problems/trade-offs that led to the revert — so it can be avoided in future apps.

---

## 2. What Was Implemented

### 2.1 Backend — `StaticFiles(html=True)` Mount

**Before (manual SPA catch-all):**

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

# Mount only /assets for hashed static files
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

# Catch-all route for SPA
@app.get("/{full_path:path}")
async def serve_spa(full_path: str) -> FileResponse:
    if full_path.startswith(("api/", "health")):
        raise HTTPException(status_code=404, detail="Not found")
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(FRONTEND_DIR / "index.html")
```

**After (StaticFiles mount — the reverted change):**

```python
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

# Configurable static dir via Settings
static_dir = Path(settings.static_dir) if settings.static_dir else FRONTEND_DIR

# Single mount at root (must be LAST — catch-all)
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    logger.info("Serving frontend static files from %s", static_dir)
```

### 2.2 Configuration — `STATIC_DIR` Setting

Added a `static_dir` field to the centralized `Settings(BaseSettings)` class:

```python
static_dir: str = Field(
    default="",
    description="Path to frontend static build directory (empty = disabled)",
)
```

This was propagated to:
- `.env.example` — `STATIC_DIR=frontend/dist`
- `local.settings.example.json` — `"STATIC_DIR": "frontend/dist"`
- `local.settings.json` — `"STATIC_DIR": "frontend/dist"`

### 2.3 Docker Compose — Volume Mount

```yaml
services:
  backend:
    environment:
      STATIC_DIR: /app/static
    volumes:
      - ./frontend/dist:/app/static:ro   # read-only mount of built frontend
```

---

## 3. How `StaticFiles(html=True)` Works

Starlette's `StaticFiles` with `html=True`:

1. **Exact file match** — if the request path matches a file on disk, serve it.
2. **Append `.html`** — if no match, try `{path}.html`.
3. **Directory index** — if path is a directory, serve `index.html` inside it.
4. **Fallback** — if path has no extension and no file is found, serve the root `index.html` (SPA fallback).
5. **404** — if none of the above match, return 404.

This effectively replaces the manual catch-all route for SPA history-mode routing.

---

## 4. Why It Was Reverted — Problems and Trade-offs

### 4.1 Route Shadowing Risk

Mounting `StaticFiles` at `/` as a catch-all means **every request not matched by an API router falls through to the static file handler**. This creates subtle issues:

- **Debugging confusion** — a typo in an API URL silently serves `index.html` instead of returning a clear 404 from the API layer.
- **Future route conflicts** — any new top-level mount (e.g., `/docs`, `/metrics`, `/webhooks`) must be carefully ordered before the `StaticFiles` mount, or it will be shadowed.
- **Health/readiness probes** — probes hitting non-API paths could receive `index.html` with a 200 status instead of the intended health check response.

### 4.2 Loss of Explicit Control

The manual catch-all provides explicit control over:

- **Which paths are API vs. SPA** — the `startswith(("api/", "health"))` guard clearly separates concerns.
- **Response headers** — `FileResponse` allows custom cache headers per file type; `StaticFiles` uses Starlette defaults.
- **Error behavior** — custom 404s for missing API routes vs. SPA fallback are explicit in the handler.

### 4.3 Docker Complexity

The pattern introduced an extra read-only volume mount (`./frontend/dist:/app/static:ro`) and an env var (`STATIC_DIR`) just to wire the same directory that was already available via the filesystem. This adds:

- An extra config surface to maintain across `.env.example`, `local.settings.json`, `docker-compose.yaml`.
- A deployment coupling between the frontend build output and backend container.

### 4.4 Config Parity Overhead

A new `STATIC_DIR` env var had to be added to 4 files (`.env.example`, `local.settings.example.json`, `local.settings.json`, `docker-compose.yaml`) and the `Settings` class — all for a feature that the manual approach handles with zero configuration.

---

## 5. When `StaticFiles` Mount IS Appropriate

The `StaticFiles(html=True)` pattern is not inherently bad. It works well when:

| Scenario | Why It Works |
|----------|-------------|
| **Dedicated static-only server** | No API routes to conflict with. |
| **Mounted at a sub-path** (e.g., `/app/`) | No root-level shadowing. |
| **Simple apps with few routes** | Minimal risk of route confusion. |
| **Reverse proxy handles SPA fallback** | Nginx/Caddy serves static files; FastAPI only handles `/api/*`. |

---

## 6. Recommended Pattern (What We Use Instead)

For this project, the manual SPA catch-all is preferred:

```python
# Mount only hashed assets at /assets
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

# Explicit SPA catch-all with API guard
@app.get("/{full_path:path}")
async def serve_spa(full_path: str) -> FileResponse:
    if full_path.startswith(("api/", "health")):
        raise HTTPException(status_code=404, detail="Not found")
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(FRONTEND_DIR / "index.html")
```

**Advantages:**
- Explicit API vs. SPA boundary.
- No extra config, no extra volume mounts.
- Custom response headers and error handling possible per path.
- Works identically in local dev and Docker without env var differences.

---

## 7. Checklist: Avoid This Pattern in New Apps

Before adopting `StaticFiles(html=True)` at root in a FastAPI app, verify:

- [ ] The app has **no API routes** that could be shadowed.
- [ ] There is **no health/readiness probe** that could receive HTML instead of JSON.
- [ ] You **do not need** per-file cache control headers.
- [ ] You **accept** that 404s for bad URLs will return `index.html` (200) instead of a proper error.
- [ ] The deployment model **requires** configurable static directory paths.
- [ ] A reverse proxy (Nginx, Caddy, Azure Front Door) is **not available** to handle static serving.

If any box is unchecked, use the manual SPA catch-all pattern instead.

---

## 8. Files Affected (for Reference)

| File | Change | Reverted? |
|------|--------|-----------|
| `backend/src/main.py` | Replaced manual SPA route with `StaticFiles(html=True)` mount at `/` | Yes |
| `backend/src/config.py` | Added `static_dir` field to `Settings` | Yes |
| `.env.example` | Added `STATIC_DIR=frontend/dist` | Yes |
| `local.settings.example.json` | Added `"STATIC_DIR": "frontend/dist"` | Yes |
| `local.settings.json` | Added `"STATIC_DIR": "frontend/dist"` | Yes |
| `docker-compose.yaml` | Added `STATIC_DIR` env var + `./frontend/dist:/app/static:ro` volume | Yes |
| `frontend/vite.config.ts` | Added favicon cache-buster plugin | No (kept) |
| `frontend/index.html` | Added `?v=__FAVICON_HASH__` to favicon link | No (kept) |
| `frontend/package.json` | Upgraded vitest to `^4.1.0` | No (kept) |
