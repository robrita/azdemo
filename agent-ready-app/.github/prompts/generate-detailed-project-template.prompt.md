---
description: "Generate or upgrade a full-stack project template package that preserves this repo's architecture, rules, theming, runtime, env, serverless, container, and Cosmos DB best practices"
name: "Generate Detailed Project Template"
argument-hint: "Describe the target app/template to generate or refine"
agent: "agent"
---

# Generate Or Upgrade A Detailed Project Template

Create or refine a **portable, reproducible full-stack project template** based on the standards established in this repository.

Your job is not to produce a shallow starter. Build or upgrade a template package that can be copied into a fresh repository and still instruct an agent exactly how to create the app correctly.

This prompt always requires both:

1. a documentation package that explains the template contract in detail
2. runnable starter code and starter assets that implement that contract

## Primary Goal

Produce a project template that captures this repository's engineering standards in enough detail that a new project can inherit:

- backend architecture and layering
- frontend architecture and centralized theming
- root-level local development workflow
- Docker-based local reproducibility
- Azure Functions ASGI hosting support
- container deployment compatibility
- configuration and environment file conventions
- quality gates and CI expectations
- async coding rules
- dependency pinning rules
- Cosmos DB rules when Cosmos is used
- reusable starter code, starter config files, and bootstrap automation

## Expected Output

Create or update a template package with **both documentation and implementation assets**.

Both parts are mandatory. Do not stop at documentation only, and do not produce starter code without the corresponding template contract docs.

The final result should include, where applicable:

1. A portable template contract:
- `template/README.md`
- `template/AGENTS.md`
- `template/.rules/*.md`
- `template/structure/project-tree.md`
- `template/backend/*.md`
- `template/frontend/*.md`
- `template/deployment/*.md`
- `template/tooling/*.md`
- `template/placeholders/*.md`
- `template/verification/*.md`

2. Starter config files:
- root `.env.example`
- root `.env`
- `frontend/.env.example`
- `frontend/.env.local`
- `local.settings.example.json`

3. A ready-to-bootstrap starter project:
- root `Makefile`
- root `docker-compose.yaml`
- root `pyproject.toml`
- root `requirements.txt` when Azure Functions packaging needs it
- root `function_app.py`
- root `host.json`
- backend starter app
- frontend starter app
- tests
- CI workflow
- bootstrap script

## Non-Negotiable Requirements

### 1. Backend Stack And Shape

The backend must use:

- Python 3.12+
- FastAPI
- async-first code paths
- centralized typed config through `Settings(BaseSettings)`
- thin route handlers
- route -> service -> repository -> data client layering
- lifespan-managed long-lived clients and startup validation
- structured logging and correlation ID propagation
- `/health`, `/health/live`, and `/health/ready`

The backend must be runnable from the **repository root** during local development.

That means:

- `make dev` starts FastAPI from the root directory
- root `.env.example` and root `.env` exist
- backend config loading works from the root directory without requiring `cd backend`
- Docker Compose uses the same root env source by default

### 2. Frontend Stack And Shape

The frontend must use:

- React
- TypeScript
- Vite
- Tailwind CSS
- centralized semantic theme tokens
- global component classes in CSS
- dark-mode compatibility
- feature-oriented structure

The frontend must include:

- `frontend/.env.example`
- `frontend/.env.local`
- Vite proxy support for local API access
- centralized theme assets such as `tailwind.config.js`, `src/theme/tokens.ts`, and `src/index.css`

### 3. Mandatory Platform And Deployment Modes

Preserve support for all of these in every generated template:

1. Azure Function App via Azure Functions v2 `AsgiFunctionApp`
2. container-based deployment using the same FastAPI app under `uvicorn`
3. Azure Cosmos DB as the mandatory primary data store

The Azure Functions wrapper must remain a **thin hosting adapter**. Do not put business logic into `function_app.py`.

Do not treat Azure Functions, container deployment, or Cosmos DB as optional in the generated template.

### 4. Runtime And Reproducibility

The template must preserve:

- Docker Compose as the default full-stack local runtime
- root `make` targets for backend, frontend, docker, and CI workflows
- explicit health endpoints
- explicit timeout and retry expectations
- stateless request handling where appropriate
- cross-platform compatibility for Windows and Linux development

### 5. Async And Parallel Execution Standards

Carry over the async conventions from this repo:

- use `async def` for I/O code paths
- use `aiohttp` for outbound HTTP calls
- use `asyncio.gather()` for independent parallel async work
- avoid thread-pool-based substitutes for normal async I/O orchestration
- handle `asyncio.gather(..., return_exceptions=True)` safely with type guards

### 6. Configuration And Environment Rules

Carry over the config management rules from this repo:

- one backend `Settings(BaseSettings)` source of truth
- no scattered `os.getenv()` calls
- `SecretStr` for secrets
- fail-fast validation for invalid production settings
- keep config parity across:
  - root `.env.example`
  - root `.env`
  - `local.settings.example.json`
  - local `local.settings.json` when used
  - `docker-compose.yaml`
  - backend settings code
  - docs
- frontend env vars must use the `VITE_` prefix and remain separate from backend config

### 7. Dependency Rules

Carry over the dependency rules from this repo:

- backend dependencies pinned with exact `==` versions
- no loose version ranges in backend Python dependencies
- runtime and dev dependencies clearly separated
- reproducible frontend installs

### 8. API And Error Handling Rules

Carry over the API conventions from this repo:

- Pydantic schemas for request and response validation
- typed exception hierarchy with centralized handlers
- actionable error messages
- consistent HTTP status codes
- thin route handlers
- scoped access enforcement when domain data requires it

### 9. Code Reuse And Pattern Rules

Carry over the code-pattern rules from this repo:

- reuse existing helpers before creating new ones
- centralize dependency injection providers
- use repository abstractions
- keep models and schemas clearly separated
- remove deprecated settings and feature leftovers completely, including docs and config

### 10. Cosmos DB Rules

The generated template always uses Azure Cosmos DB, so include the Cosmos DB standards explicitly.

That includes:

- camelCase document field naming
- query paths matching serialized aliases
- parameterized queries
- reserved-word escaping using `c["field"]`
- no `/id/?` in custom included indexing paths
- singleton IDs following a collision-safe pattern such as `{type}:{key}`
- singleton Cosmos client usage
- async SDK usage
- retry-aware 429 handling
- partition-key and query-pattern guidance
- indexing and projection guidance
- repository and container setup conventions aligned to Cosmos DB usage
- env, local settings, and Docker wiring for Cosmos DB access

## Source Files To Reuse And Reconcile

Use these workspace files as the baseline source of truth and preserve their important patterns:

- [AGENTS.md](../../AGENTS.md)
- [.rules/ARCHITECTURE.md](../../.rules/ARCHITECTURE.md)
- [.rules/ASYNC_PATTERNS.md](../../.rules/ASYNC_PATTERNS.md)
- [.rules/FRONTEND_THEME.md](../../.rules/FRONTEND_THEME.md)
- [.rules/RUNTIME.md](../../.rules/RUNTIME.md)
- [.rules/SERVERLESS.md](../../.rules/SERVERLESS.md)
- [.rules/CONFIG_MANAGEMENT.md](../../.rules/CONFIG_MANAGEMENT.md)
- [.rules/DEPENDENCIES.md](../../.rules/DEPENDENCIES.md)
- [.rules/API_STANDARDS.md](../../.rules/API_STANDARDS.md)
- [.rules/PATTERNS.md](../../.rules/PATTERNS.md)
- [.rules/COSMOS_FIELD_NAMING.md](../../.rules/COSMOS_FIELD_NAMING.md)
- [.rules/QUALITY_GATES.md](../../.rules/QUALITY_GATES.md)
- [Makefile](../../Makefile)
- [docker-compose.yaml](../../docker-compose.yaml)
- [pyproject.toml](../../pyproject.toml)
- [requirements.txt](../../requirements.txt)
- [function_app.py](../../function_app.py)
- [host.json](../../host.json)
- [.env.example](../../.env.example)
- [local.settings.example.json](../../local.settings.example.json)
- [frontend/package.json](../../frontend/package.json)
- [frontend/vite.config.ts](../../frontend/vite.config.ts)
- [frontend/tailwind.config.js](../../frontend/tailwind.config.js)
- [frontend/eslint.config.js](../../frontend/eslint.config.js)
- [frontend/tsconfig.json](../../frontend/tsconfig.json)
- [frontend/postcss.config.js](../../frontend/postcss.config.js)
- [frontend/.env.example](../../frontend/.env.example)
- [frontend/src/index.css](../../frontend/src/index.css)
- [frontend/src/theme/tokens.ts](../../frontend/src/theme/tokens.ts)
- [backend/src/config.py](../../backend/src/config.py)
- [backend/src/main.py](../../backend/src/main.py)

Also reconcile against any existing template assets already present under `template/`.

## Procedure

### 1. Discover And Diff

Read the current `template/` package and compare it against the repo rules and implementation patterns. Identify anything missing, weakened, contradictory, or overly generic.

### 2. Upgrade The Template Contract

Update the template documentation so it fully captures the repo's real standards rather than a simplified summary.

### 3. Upgrade The Starter Assets

If starter code or starter files exist, make them consistent with the documented contract. Do not leave starter code lagging behind the rules.

### 4. Preserve Root-Level Dev Workflow

Ensure the generated project supports:

- backend local dev from the root directory
- frontend local dev from the root directory
- root env files for backend and Docker
- frontend env files for Vite

### 5. Validate Coverage

Before finishing, verify that the resulting template explicitly covers:

- architecture
- async rules
- frontend theme rules
- runtime and Docker rules
- serverless and container rules
- config and env parity rules
- dependency pinning
- API standards
- reuse patterns
- quality gates
- mandatory Cosmos DB rules
- starter project and bootstrap flow
- mandatory Azure Functions support
- mandatory container deployment support
- both documentation assets and runnable starter assets

### 6. Report Gaps Honestly

If any remaining issue cannot be resolved within the workspace, say exactly what is blocked and why. Do not claim the template is complete if key standards are still only partially encoded.

## Output Format

Return:

1. What was added or updated
2. Which repo standards are now captured explicitly
3. Any remaining weak spots or unresolved issues
4. The most important files to review first

Prefer implementation over theory. If the request asks for a template, create or update the actual files.
