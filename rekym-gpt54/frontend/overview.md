# Frontend Overview

The frontend starter is intentionally small but preserves the required shape.

## Included behaviors

- React + TypeScript + Vite + Tailwind CSS.
- Feature-oriented layout under `src/features/`.
- Shared semantic theme tokens and reusable CSS component classes.
- Dark mode toggle.
- Local API proxy support.
- Dashboard feature that reads backend health and merchant data.
- Frontend telemetry client pointed at the backend intake endpoint.

## Extension guidance

- Put feature-specific screens and hooks under `src/features/<feature-name>/`.
- Keep app shell and providers under `src/app/`.
- Keep theme maps and semantic tokens centralized.