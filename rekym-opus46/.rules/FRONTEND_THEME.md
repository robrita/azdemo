# Frontend Theme & Styling

## Architecture

| Layer | File | Purpose |
|-------|------|---------|
| Design tokens | `frontend/tailwind.config.js` | `primary`, `surface` color scales; fonts |
| Shared color maps | `frontend/src/theme/tokens.ts` | Status/severity style maps |
| Base defaults | `frontend/src/index.css` `@layer base` | Body bg, link colors, focus rings |
| Component classes | `frontend/src/index.css` `@layer components` | `.btn-*`, `.card`, `.badge-*`, `.spinner` |

## Color System

- **Primary (`primary-*`)**: Brand blue — primary actions, navigation, trust anchor
- **Navy (`navy-*`)**: Deep text & heading color (NOT generic gray)
- **Surface**: Blue-tinted neutral backgrounds
- **Success/Warning/Error/Info**: Semantic colors for status indicators

## Rules

1. **No hardcoded `blue-*` or `indigo-*`** for brand/interactive colors — use `primary-*` tokens
2. **Use component classes** (`.btn-primary`, `.card`, etc.) before writing custom Tailwind utilities
3. **Import from `theme/tokens.ts`** for status/severity badges — never duplicate inline maps
4. **Use `dark:` variants** for all hardcoded colors (dark mode compatibility)

## How New Pages Inherit Theme

Unstyled elements auto-inherit styling from `@layer base`:
- **Body**: `bg-surface`, `text-navy-900`
- **Headings**: `font-display` (Gilroy/Inter), `font-semibold`
- **Links**: `text-primary-600` with `hover:text-primary-700`
- **Focus rings**: `ring-2 ring-primary-500 ring-offset-2`

## Available Component Classes

- **Buttons**: `.btn-primary`, `.btn-secondary`, `.btn-tertiary`, `.btn-danger`
- **Cards**: `.card`, `.card-hover`
- **Layout**: `.page-container`, `.page-title`
- **Badges**: `.badge`, `.badge-primary`, `.badge-success`, `.badge-warning`, `.badge-danger`
- **Navigation**: `.nav-link`, `.nav-link-active`
- **Feedback**: `.spinner`
- **Tables**: `.table-header`, `.table-row-hover`

## Dark Mode

Every component must work in both light and dark mode. Use `dark:` Tailwind variants for all hardcoded colors. CSS custom properties in `:root.dark` handle the switch automatically.
