---
description: "Update AGENTS.md and all .rules/ files to match the actual project — removes template leftovers, aligns with real tech stack and domain"
agent: "agent"
---

# Update AGENTS.md & .rules/ from Project Template

The workspace `AGENTS.md` and `.rules/*.md` files were copied from another project or template. Reconcile every file with the **actual** codebase so agents receive accurate context.

## Inputs

- `AGENTS.md` — the top-level agent guideline map
- `.rules/*.md` — all topic docs referenced from AGENTS.md

## Procedure

### 1. Discover the real project

Scan the workspace to build a factual picture. Read in parallel where possible.

**Project identity files** (read first):
- `AGENTS.md` — current title, rules, navigation
- `.rules/*.md` — every topic doc; note which reference stale concepts
- `README.md` or equivalent — stated purpose

**Backend** (adapt to whatever exists):
- Package manifests — `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `Gemfile`, `*.csproj`, etc.
- Entry point — `main.py`, `app.py`, `main.go`, `Program.cs`, `index.ts`, etc.
- Config / settings — env loaders, settings classes, config files
- Domain models / entities — ORMs, schemas, Pydantic models, types, structs
- Data access layer — repositories, DAOs, query builders, migrations
- Route / controller layer — handlers, controllers, routers, endpoints
- Service / business logic layer — service classes, use cases
- Middleware — auth, rate limiting, logging, tenant scoping
- Integration / external services — API clients, SDK wrappers

**Frontend** (if present):
- `package.json` (or equivalent) — framework, scripts, dependencies
- App entry / router — `App.tsx`, `App.vue`, `main.ts`, routing config
- Feature / page directories — discover the feature structure
- Theme / design tokens — token files, CSS variables, Tailwind config

**Infrastructure**:
- `docker-compose.yaml`, `Dockerfile`(s), `Procfile`, `serverless.yml`, `terraform/`, `bicep/`, `k8s/`, CF templates, etc.
- `Makefile`, `Taskfile.yml`, `justfile`, `package.json` scripts, `Rakefile`, CI config
- Specs / docs directories — for domain context

### 2. Build a project profile

From step 1, answer these questions (the answers drive every edit):

| Question | Examples |
|----------|----------|
| **Name & purpose** | "Inventory tracker", "Compliance platform", "Chat app" |
| **Languages & frameworks** | Python/FastAPI, Go/Gin, .NET/ASP.NET, Rust/Axum, Node/Express, Ruby/Rails, Java/Spring |
| **Database(s)** | Cosmos DB, PostgreSQL, MongoDB, DynamoDB, SQLite, Redis, Firestore |
| **Deployment model** | Docker Compose, Kubernetes, serverless (Lambda/Functions), PaaS (App Service/Heroku), bare metal |
| **Domain concepts** | The key business entities and workflows (e.g. "orders & fulfillment", "cases & reviews") |
| **Dependency management** | Which manifest files, single vs multi, lock files |
| **API style** | REST, GraphQL, gRPC, tRPC, WebSocket |
| **Auth model** | JWT, OAuth, API key, session, SSO, none |
| **Build / task runner** | Make, npm scripts, Gradle, Cargo, Task, Just |
| **Test framework(s)** | pytest, Jest, Vitest, Go test, xUnit, RSpec, JUnit |
| **Frontend** | React, Vue, Svelte, Angular, HTMX, none |

### 3. Audit AGENTS.md

Check each section against the project profile:

| Section | Checks |
|---------|--------|
| **Title & description** | Matches actual project name, tech stack, and purpose |
| **Critical rules** | Every rule relates to tooling/patterns that actually exist. Remove rules about absent concepts (e.g. "serverless" in a Docker project, "sync requirements.txt" when only one manifest exists) |
| **Navigation table** | Every link resolves to a real file in `.rules/`. No dead links. No missing entries for `.rules/` files that exist but aren't listed |
| **Self-governance** | References only tools and commands that exist |

If there is a line-count governance rule (e.g. "under 120 lines"), respect it.

### 4. Audit each `.rules/*.md` file

For **every** `.rules/*.md` file, check:

| Check | What to Look For |
|-------|-----------------|
| **Project name & domain terms** | Any mention of the old/template project name or its domain concepts |
| **Framework & runtime patterns** | Code snippets, decorators, imports, types that belong to a different framework |
| **File paths** | Directory structures that don't match the actual workspace |
| **Dependency management** | References to manifest files or package managers that aren't used |
| **Database references** | Table/container/collection names, field naming conventions, query syntax that doesn't match the real DB |
| **Code examples** | Every snippet should be copy-pasteable in this project — right imports, right decorators, right types |
| **Build/task runner commands** | Referenced `make`, `npm`, `cargo`, etc. targets must actually exist |
| **Frontend specifics** | Theme file names, component patterns, import paths matching the real frontend |

### 5. Apply changes to AGENTS.md

- Rewrite title, description, and tech stack line
- Rewrite critical rules to reflect actual project constraints and patterns
- Update navigation table — add missing, remove dead, fix links
- Remove references to non-existent files, tools, or commands
- Add new rules for project-specific patterns discovered in step 2

### 6. Apply changes to each `.rules/*.md` file

For each file, rewrite to be **project-accurate**:

- Replace old project name and domain terms with actual ones
- Replace old framework/runtime patterns with actual ones
- Update all file paths to match real directory structure
- Rewrite code examples using the project's actual imports, types, and conventions
- Update database references (container/table names, field naming, query patterns)
- Update dependency examples to match actual manifests and versions

**When a file covers an absent concept entirely** (e.g. `SERVERLESS.md` in a containerized project):
- **Repurpose** if there's an analogous concept in the real project (e.g. → containerized runtime)
- **Flag for user** if no equivalent exists — ask whether to delete or repurpose

### 7. Cross-reference verification

After all edits, search `AGENTS.md` and `.rules/*.md` for stale leftovers:

- Old project name or domain terms from the template
- Framework-specific patterns that belong to the template's stack, not this project's
- File paths that don't exist in the workspace
- Manifest file references that don't apply
- Tool or command names that aren't installed or configured

Fix any remaining hits. The goal is **zero stale references**.

### 8. Report summary

Output a concise changelog grouped by file:

```
**AGENTS.md:**
- Changed: (what was updated and why)
- Added: (new rules or navigation entries)
- Removed: (stale rules or entries)

**.rules/<FILE>.md:** (repeat for each modified file)
- Changed: ...
- Added: ...
- Removed: ...

**Cross-reference verification:** ✅ No stale references found
```
