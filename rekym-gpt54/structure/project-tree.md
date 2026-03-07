# Project Tree

```text
template/
|-- AGENTS.md
|-- README.md
|-- .env.example
|-- .env
|-- .github/
|   `-- workflows/ci.yml
|-- .rules/
|   |-- API_STANDARDS.md
|   |-- ARCHITECTURE.md
|   |-- ASYNC_PATTERNS.md
|   |-- CHECKLIST.md
|   |-- CONFIG_MANAGEMENT.md
|   |-- COSMOS_FIELD_NAMING.md
|   |-- DEPENDENCIES.md
|   |-- FRONTEND_THEME.md
|   |-- QUALITY_GATES.md
|   |-- RUNTIME.md
|   `-- SERVERLESS.md
|-- Makefile
|-- backend/
|   |-- Dockerfile
|   |-- src/
|   |   |-- config.py
|   |   |-- dependencies.py
|   |   |-- exceptions.py
|   |   |-- main.py
|   |   |-- cosmos/client.py
|   |   |-- lib/observability.py
|   |   |-- middleware/auth.py
|   |   |-- models/
|   |   |-- repositories/
|   |   |-- routes/
|   |   |-- schemas/
|   |   `-- services/
|   `-- tests/test_health.py
|-- deployment/
|   `-- overview.md
|-- docker-compose.yaml
|-- frontend/
|   |-- Dockerfile
|   |-- .env.example
|   |-- .env.local
|   |-- package.json
|   |-- postcss.config.js
|   |-- tailwind.config.js
|   |-- tsconfig.json
|   |-- vite.config.ts
|   |-- src/
|   |   |-- app/
|   |   |-- components/
|   |   |-- features/dashboard/
|   |   |-- services/
|   |   |-- theme/
|   |   |-- index.css
|   |   |-- main.tsx
|   |   `-- vite-env.d.ts
|   `-- tests/tokens.test.ts
|-- function_app.py
|-- host.json
|-- local.settings.example.json
|-- placeholders/README.md
|-- pyproject.toml
|-- requirements.txt
|-- scripts/
|   |-- bootstrap.ps1
|   `-- bootstrap.sh
|-- tooling/
|   `-- overview.md
`-- verification/
    `-- checklist.md
```