# Favicon Setup — FastAPI + Vite (React) Full-Stack App

How to add a custom favicon to a full-stack app where FastAPI serves the built
frontend via `StaticFiles` and Vite builds the React SPA.

---

## Problem

In a FastAPI + React setup where the backend serves the frontend build output,
favicons often fail to render because:

1. **SPA catch-all returns HTML for every path** — a hand-written fallback route
   serves `index.html` for _all_ unmatched paths, including `/favicon.png`.
   The browser receives HTML with `Content-Type: text/html` instead of the
   actual image.
2. **Browser caching** — even after fixing the backend, browsers cache the old
   broken response (404 or HTML body) and never re-request the real file.

---

## Solution (3 layers)

### Layer 1 — Backend: `StaticFiles(html=True)` mount

Use Starlette's built-in `StaticFiles` with `html=True` instead of a custom
SPA fallback route. This serves real files with correct MIME types **and**
falls back to `index.html` only when the requested path doesn't match a file.

**`backend/src/main.py`** — at the end of `create_app()`, after all routers:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Serve frontend static build (must be LAST — catch-all mount)
static_dir = Path(settings.static_dir) if settings.static_dir else None
if static_dir and static_dir.is_dir():
    application.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    logger.info("Serving frontend static files from %s", static_dir)
```

Key points:
- **Must be the last mount** — `StaticFiles("/")` is a catch-all; any routers
  registered after it will be shadowed.
- **`html=True`** — enables SPA mode: serves `index.html` for paths that
  don't resolve to a real file, while still serving real static assets
  (images, CSS, JS) with correct Content-Type headers.
- **Conditional** — only mounts if `STATIC_DIR` is set and the directory
  exists. In dev mode (frontend on port 5173 via Vite proxy), leave it empty.

**`backend/src/config.py`** — add `static_dir` to Settings:

```python
static_dir: str = Field(
    default="",
    description="Path to frontend static build directory (empty = disabled)",
)
```

### Layer 2 — Config: set `STATIC_DIR` everywhere

| File | Value | Notes |
|------|-------|-------|
| `.env` | `STATIC_DIR=frontend/dist` | Local dev (backend runs from project root) |
| `.env.example` | `STATIC_DIR=frontend/dist` | Template for new clones |
| `local.settings.json` | `"STATIC_DIR": "frontend/dist"` | Azure Functions local dev |
| `local.settings.example.json` | `"STATIC_DIR": "frontend/dist"` | Template |
| `docker-compose.yaml` | `STATIC_DIR=/app/static` | Container path (see volume mount) |

Docker Compose volume mount to make the frontend build available to the backend
container:

```yaml
services:
  backend:
    environment:
      - STATIC_DIR=/app/static
    volumes:
      - ./frontend/dist:/app/static:ro
```

### Layer 3 — Frontend: favicon file + cache-busting Vite plugin

#### 3a. Place the favicon

Put the favicon image in the Vite `public/` directory so it gets copied to
`dist/` unchanged during build:

```
frontend/public/favicon.png
```

Download example:

```powershell
Invoke-WebRequest -Uri "<favicon-url>" -OutFile "frontend/public/favicon.png"
```

#### 3b. Reference in `index.html` with a placeholder

```html
<link rel="icon" type="image/png" href="/favicon.png?v=__FAVICON_HASH__" />
```

The `__FAVICON_HASH__` placeholder is replaced at build time by a Vite plugin
(see 3c). This forces browsers to fetch the real file instead of using a stale
cached response.

#### 3c. Vite cache-buster plugin

**`frontend/vite.config.ts`**:

```ts
import crypto from "node:crypto";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

function faviconCacheBuster(): Plugin {
  const hash = crypto.randomBytes(3).toString("hex").slice(0, 5);
  return {
    name: "favicon-cache-buster",
    transformIndexHtml(html) {
      return html.replace("__FAVICON_HASH__", hash);
    },
  };
}

export default defineConfig({
  plugins: [react(), faviconCacheBuster()],
  // ... rest of config
});
```

Every `npm run build` generates a unique 5-character hex hash (e.g., `e231e`),
producing output like:

```html
<link rel="icon" type="image/png" href="/favicon.png?v=e231e" />
```

---

## Step-by-step checklist for a new app

1. **Download favicon** to `frontend/public/favicon.png`
2. **Update `frontend/index.html`** — set the `<link rel="icon">` href to
   `/favicon.png?v=__FAVICON_HASH__`
3. **Add the `faviconCacheBuster` plugin** to `frontend/vite.config.ts`
4. **Add `static_dir` field** to your `Settings(BaseSettings)` class in
   `backend/src/config.py`
5. **Mount `StaticFiles`** at the end of `create_app()` in
   `backend/src/main.py` (after all routers)
6. **Set `STATIC_DIR`** in `.env`, `.env.example`, `local.settings.json`,
   `local.settings.example.json`, and `docker-compose.yaml`
7. **Build frontend** — `cd frontend && npm run build`
8. **Restart backend** and hard-refresh browser (Ctrl+Shift+R)
9. **Verify** — `curl -I http://localhost:8000/favicon.png` should return
   `Content-Type: image/png` with the correct file size

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Favicon shows default browser icon | `STATIC_DIR` is empty or directory doesn't exist | Set the env var and run `npm run build` |
| Favicon returns HTML content | Custom SPA fallback overrides real file | Replace with `StaticFiles(html=True)` |
| Favicon doesn't update after change | Browser cached old response | Cache-buster plugin + hard refresh |
| Works on 5173 but not 8000 | Backend not serving static files | Verify `StaticFiles` mount and `STATIC_DIR` |
| Docker: favicon 404 | Volume not mounted or wrong `STATIC_DIR` path | Check `docker-compose.yaml` volume + env |

---

## File inventory

```
frontend/
  public/
    favicon.png          ← source image (copied to dist/ on build)
  index.html             ← <link> with __FAVICON_HASH__ placeholder
  vite.config.ts         ← faviconCacheBuster() plugin
  dist/
    favicon.png          ← built copy (served by backend)
    index.html           ← href="/favicon.png?v=<hash>"

backend/
  src/
    config.py            ← static_dir: str setting
    main.py              ← StaticFiles(directory=static_dir, html=True) mount

.env                     ← STATIC_DIR=frontend/dist
docker-compose.yaml      ← STATIC_DIR=/app/static + volume mount
```
