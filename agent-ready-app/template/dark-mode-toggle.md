# Dark Mode with Local Persistence — React + Tailwind CSS

Add a two-state (light / dark) theme toggle to a React + Tailwind CSS app.
The user's choice is saved to `localStorage`. When no preference is stored,
the app follows the operating system's `prefers-color-scheme` setting.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Framework** | React 18+ (uses `useSyncExternalStore`) |
| **CSS** | Tailwind CSS 3+ with `darkMode: "class"` |
| **Build tool** | Vite (or any tool that serves `index.html`) |

No additional npm dependencies are required.

---

## How it works

```
┌────────────────────────────────────────────────────────┐
│  Page load (index.html inline script)                  │
│  ┌──────────────────────────────────────┐              │
│  │ localStorage("theme") exists?        │              │
│  │   YES → use stored value             │              │
│  │   NO  → check prefers-color-scheme   │              │
│  │ If dark → add class="dark" to <html> │              │
│  └──────────────────────────────────────┘              │
│                                                        │
│  React hydrates                                        │
│  ┌──────────────────────────────────────┐              │
│  │ useTheme() hook                      │              │
│  │   • reads resolved theme             │              │
│  │   • subscribes to OS media changes   │              │
│  │   • subscribes to cross-tab storage  │              │
│  │   • exposes toggle() function        │              │
│  └──────────────────────────────────────┘              │
│                                                        │
│  User clicks toggle                                    │
│  ┌──────────────────────────────────────┐              │
│  │ 1. Compute opposite of current theme │              │
│  │ 2. Write to localStorage("theme")    │              │
│  │ 3. Toggle class="dark" on <html>     │              │
│  │ 4. Notify React subscribers          │              │
│  └──────────────────────────────────────┘              │
└────────────────────────────────────────────────────────┘
```

### Resolution priority

| Priority | Source | When |
|---|---|---|
| 1 (highest) | `localStorage.getItem("theme")` | User has clicked the toggle at least once |
| 2 (fallback) | `window.matchMedia("(prefers-color-scheme: dark)")` | No stored preference |

### Persistence details

| Key | `"theme"` |
|---|---|
| Values | `"light"` or `"dark"` |
| Absent | Follow OS preference |
| Scope | Per-origin (`localStorage`) |
| Cross-tab | Synced via `StorageEvent` listener |

---

## Setup

### 1. Configure Tailwind for class-based dark mode

**`tailwind.config.js`**:

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // your tokens...
    },
  },
};
```

### 2. Define CSS custom properties for both modes

**`index.css`** (or your global stylesheet):

```css
:root {
  --color-primary: #007cff;
  --color-primary-hover: #005ce5;
  --color-surface: #f6f9fd;
  --color-surface-alt: #eef2f9;
  --color-surface-card: #ffffff;
  --color-border: #e0e8f3;
  --color-text: #0a2757;
  --color-text-secondary: #445c85;
  --color-text-muted: #7e96be;
  --color-success: #27c990;
  --color-warning: #f9a60b;
  --color-error: #d61b2c;
  --color-info: #10bcb4;
  --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.08);
  color-scheme: light;
}

:root.dark {
  --color-primary: #3b9cff;
  --color-primary-hover: #007cff;
  --color-surface: #0b1929;
  --color-surface-alt: #0f2137;
  --color-surface-card: #132d4a;
  --color-border: #1e3a5f;
  --color-text: #e0e8f3;
  --color-text-secondary: #adbddc;
  --color-text-muted: #6780a9;
  --color-success: #34d89e;
  --color-warning: #fabc3c;
  --color-error: #f87171;
  --color-info: #2dd4c8;
  --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.3);
  color-scheme: dark;
}
```

> **Tip**: Adjust tokens to match your brand. The key requirement is that
> `:root.dark` mirrors every variable from `:root` with dark-appropriate values.

### 3. Add the FOUC-prevention script to `index.html`

Place this **inline** `<script>` in `<head>`, **before** any stylesheets load,
so the correct class is on `<html>` before the first paint:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My App</title>

    <!-- Prevent flash of wrong theme (FOUC) -->
    <script>
      (function () {
        var stored = localStorage.getItem('theme');
        var dark =
          stored === 'dark' ||
          (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (dark) document.documentElement.classList.add('dark');
      })();
    </script>

    <!-- stylesheets / fonts after this point -->
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

> **Why inline?** An external script would be fetched asynchronously and could
> miss the first paint, causing a flash. The inline snippet runs synchronously
> before the browser renders anything.

### 4. Create the `useTheme` hook

**`src/hooks/use-theme.ts`**:

```ts
import { useCallback, useEffect, useSyncExternalStore } from "react";

const STORAGE_KEY = "theme";

type Theme = "light" | "dark";

/** Apply or remove the `dark` class on <html>. */
function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/** Resolve the effective theme: stored preference → system preference. */
function resolveTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

// Tiny pub/sub so useSyncExternalStore can re-render on changes.
const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
function emitChange() {
  listeners.forEach((cb) => cb());
}

let snapshot: Theme = resolveTheme();

function getSnapshot(): Theme {
  return snapshot;
}

function refresh() {
  snapshot = resolveTheme();
  applyTheme(snapshot);
  emitChange();
}

/**
 * React hook for dark-mode toggling.
 *
 * - No stored preference → follows OS `prefers-color-scheme`.
 * - Toggle saves explicit `"light"` / `"dark"` to localStorage.
 */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getSnapshot);

  // Listen to OS preference changes (matters when no stored pref).
  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (!localStorage.getItem(STORAGE_KEY)) refresh();
    };
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  // Listen for storage events from other tabs.
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) refresh();
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = resolveTheme() === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    refresh();
  }, []);

  return { theme, toggle } as const;
}
```

**Key design decisions:**

| Decision | Rationale |
|---|---|
| `useSyncExternalStore` | Tear-free reads of external mutable state (React 18 best practice). Avoids `useState` + manual sync. |
| Module-level singleton | Theme state is global — only one `<html>` element. Multiple components calling `useTheme()` share the same snapshot. |
| `StorageEvent` listener | Keeps multiple browser tabs in sync. `StorageEvent` only fires in *other* tabs, so same-tab updates go through `refresh()` directly. |
| `matchMedia` listener | When no stored preference exists, OS theme changes are reflected live without user interaction. |

### 5. Create the toggle component

**`src/components/theme-toggle.tsx`**:

```tsx
import { useTheme } from "../hooks/use-theme";

/** Sun / Moon toggle button for the header. */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="rounded-lg p-2 text-navy-600 transition-colors hover:bg-navy-100
        dark:text-[var(--color-text-secondary)] dark:hover:bg-[var(--color-surface-alt)]"
    >
      {theme === "dark" ? (
        /* Sun icon — shown in dark mode to indicate "switch to light" */
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
        >
          <circle cx={12} cy={12} r={5} />
          <line x1={12} y1={1} x2={12} y2={3} />
          <line x1={12} y1={21} x2={12} y2={23} />
          <line x1={4.22} y1={4.22} x2={5.64} y2={5.64} />
          <line x1={18.36} y1={18.36} x2={19.78} y2={19.78} />
          <line x1={1} y1={12} x2={3} y2={12} />
          <line x1={21} y1={12} x2={23} y2={12} />
          <line x1={4.22} y1={19.78} x2={5.64} y2={18.36} />
          <line x1={18.36} y1={5.64} x2={19.78} y2={4.22} />
        </svg>
      ) : (
        /* Moon icon — shown in light mode to indicate "switch to dark" */
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
        >
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}
```

**Accessibility notes:**

- `aria-label` dynamically describes the action ("Switch to dark mode" / "Switch to light mode").
- Uses semantic `<button>` with `type="button"` (not a `<div>`).
- Focus ring is inherited from the global `*:focus-visible` rule.

### 6. Place the toggle in your layout

Import and render `<ThemeToggle />` in your page header or navbar:

```tsx
import { ThemeToggle } from "../components/theme-toggle";

function Header() {
  return (
    <header className="border-b border-navy-200 bg-white px-6 py-4
      dark:border-[var(--color-border)] dark:bg-[var(--color-surface-card)]">
      <div className="mx-auto flex max-w-5xl items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-navy-900 dark:text-[var(--color-text)]">
            My App
          </h1>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
```

### 7. Apply `dark:` variants to your components

Every component that has light-mode styles needs corresponding `dark:` variants.
Use CSS custom properties for consistency:

```tsx
{/* Card example */}
<div className="rounded-xl bg-white p-6 shadow-card
  dark:bg-[var(--color-surface-card)] dark:shadow-none
  dark:border dark:border-[var(--color-border)]">
  <p className="text-navy-900 dark:text-[var(--color-text)]">
    Content here
  </p>
</div>
```

**Pattern**: Use `dark:bg-[var(--color-surface-card)]` (CSS variable) rather
than `dark:bg-slate-800` (hardcoded Tailwind color) so all dark values stay
centralized in the `:root.dark` block.

---

## File inventory

```
src/
  hooks/
    use-theme.ts          ← hook: resolveTheme, toggle, subscribe
  components/
    theme-toggle.tsx      ← UI: sun/moon icon button
index.html                ← inline FOUC-prevention script in <head>
index.css                 ← :root / :root.dark CSS custom properties
tailwind.config.js        ← darkMode: "class"
```

---

## Checklist for adopting in a new project

- [ ] `tailwind.config.js` has `darkMode: "class"`
- [ ] `:root` and `:root.dark` CSS custom properties defined in global stylesheet
- [ ] Inline FOUC-prevention `<script>` added to `<head>` in `index.html`
- [ ] `src/hooks/use-theme.ts` copied (or adapted) into the project
- [ ] `src/components/theme-toggle.tsx` copied (or adapted) — adjust class names to match your design tokens
- [ ] `<ThemeToggle />` rendered in the app layout (header/navbar)
- [ ] All components use `dark:` Tailwind variants for backgrounds, text, borders, and shadows
- [ ] Verified: page loads with correct theme (no flash)
- [ ] Verified: toggle persists across page reloads
- [ ] Verified: new tab inherits the saved preference
- [ ] Verified: clearing `localStorage("theme")` falls back to OS preference

---

## Extending to a three-way toggle (Light / Dark / System)

If you later want an explicit "System" option in the UI:

1. Store `"system"` as a third `localStorage` value (or remove the key entirely).
2. Change `resolveTheme()` to treat both absent and `"system"` the same way (already does).
3. Replace the two-state icon button with a three-segment control or dropdown.
4. The hook logic, FOUC script, and CSS layers remain unchanged.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Flash of light theme on dark-mode load | FOUC script missing or placed after stylesheet | Move inline `<script>` before any `<link>` or `<style>` tags in `<head>` |
| Toggle has no effect | `darkMode` not set to `"class"` in Tailwind config | Add `darkMode: "class"` |
| Dark mode looks broken | Missing `dark:` variants on some elements | Audit components; ensure bg, text, border, and shadow all have `dark:` overrides |
| Theme resets on reload | `localStorage` is blocked (e.g. private browsing on some browsers) | Wrap `localStorage` calls in try/catch (graceful degradation to OS preference) |
| Other tab doesn't sync | `StorageEvent` only fires in *other* windows | Same-tab updates go through `refresh()` — this is correct behavior |
