# Frontend Theme Rules

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS

## Theme contract

- Centralize semantic tokens in `frontend/src/theme/tokens.ts`.
- Define global component classes in `frontend/src/index.css`.
- Keep Tailwind brand tokens in `frontend/tailwind.config.js`.
- Support light and dark mode for every shared component and page.

## Styling rules

1. Use semantic tokens such as `primary`, `navy`, `surface`, `success`, `warning`, and `danger`.
2. Use shared classes like `.btn-primary`, `.btn-secondary`, `.card`, and `.badge-*` before creating inline utility compositions.
3. Keep typography and spacing consistent across feature modules.
4. Do not scatter status-color maps in components. Import them from `theme/tokens.ts`.
5. Frontend environment variables must use the `VITE_` prefix and stay separate from backend config.

## Feature structure

- Keep feature-specific UI under `frontend/src/features/<feature-name>/`.
- Keep app-level providers and layout under `frontend/src/app/`.
- Keep data access under `frontend/src/services/`.