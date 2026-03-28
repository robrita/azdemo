# Favicon Cache-Busting — Vite Plugin

Prevent browsers from serving a stale cached favicon by appending a unique
build-time hash to the favicon URL.

---

## How it works

1. `index.html` references the favicon with a `__FAVICON_HASH__` placeholder.
2. A small Vite plugin replaces that placeholder with a random 5-char hex
   hash on every `npm run build`.
3. Browsers see a new URL (e.g. `/favicon.png?v=e231e`) and fetch the real
   file instead of using a cached response.

---

## Setup

### 1. Place the favicon

Put the favicon image in the Vite `public/` directory so it gets copied to
`dist/` unchanged during build:

```
frontend/public/favicon.png
```

### 2. Reference in `index.html` with a placeholder

```html
<link rel="icon" type="image/png" href="/favicon.png?v=__FAVICON_HASH__" />
```

### 3. Add the Vite cache-buster plugin

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

### 4. Build and verify

```bash
cd frontend && npm run build
```

The built `dist/index.html` should contain a hashed URL:

```html
<link rel="icon" type="image/png" href="/favicon.png?v=e231e" />
```

If the favicon still doesn't update, hard-refresh the browser (Ctrl+Shift+R).

---

## File inventory

```
frontend/
  public/
    favicon.png          ← source image (copied to dist/ on build)
  index.html             ← <link> with __FAVICON_HASH__ placeholder
  vite.config.ts         ← faviconCacheBuster() plugin
  dist/
    favicon.png          ← built copy
    index.html           ← href="/favicon.png?v=<hash>"
```
