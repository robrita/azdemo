---
description: "Update a Makefile template to match the actual project structure, removing stale targets and adding missing ones"
agent: "agent"
---

# Update Makefile from Project Template

Audit the workspace Makefile and reconcile it with the **actual** codebase. The Makefile may have been copied from another project or template and contains targets that reference files, scripts, or tools that don't exist — and is missing targets for things that do. This prompt is stack-agnostic and works for any language or framework.

## Procedure

### 1. Discover the project stack

Before touching the Makefile, scan the workspace root to determine:

- **Language & package manager** — look for manifest files (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, `Gemfile`, `composer.json`, `mix.exs`, `build.gradle`, `*.csproj`, etc.)
- **Containerization** — `docker-compose.yaml`, `Dockerfile`, `Containerfile`
- **CI/CD** — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml`
- **App entry points** — main module, server binary, or framework CLI (read code to confirm import paths)
- **Script directories** — `scripts/`, `bin/`, `tools/`, or any folder containing helper scripts
- **Test layout** — test directories, runner config, and whether test markers / tags are defined
- **Sub-projects** — monorepo workspaces, frontend/backend splits, or multiple services
- **Environment config** — `.env.example`, `.env.sample`, or equivalent

Read all discovered files in parallel to build a complete picture.

### 2. Identify issues — classify each Makefile target

For every existing target, verify:

| Check | How |
|-------|-----|
| **Referenced files exist?** | Verify every script, config file, binary, and path the command invokes |
| **Tool is a declared dependency?** | Confirm each CLI tool appears in the project's manifest or lock file |
| **Paths are correct?** | App import paths, source directories, test directories, env file locations |
| **Runner flags are valid?** | Test markers/tags only if the runner config defines them; linter rules only if configured |
| **Sub-project scripts exist?** | For delegated commands (e.g. `cd sub && npm run X`, `cargo test -p Y`), confirm the target script or package exists |
| **Deploy target matches infra?** | Deployment commands match the actual platform (Docker, cloud CLI, serverless, etc.) |

Classify each target as:
- **keep** — correct as-is
- **fix** — target is valid but command, path, or flags are wrong
- **remove** — references files, scripts, or tools that don't exist

### 3. Identify missing targets

Scan the codebase for common workflows not covered by the Makefile:

- **Container orchestration** — up/down/build/logs if compose or similar config exists
- **Dependency install** — per sub-project if multiple manifests exist
- **Dev servers** — for each service or sub-project
- **Test sub-suites** — unit, integration, e2e, performance, etc. if matching directories exist
- **Lint / format / typecheck** — for each language present (backend, frontend, shared libs)
- **Database / migration** — if migration tool config or scripts exist
- **Code generation** — protobuf, GraphQL codegen, OpenAPI, etc. if generator configs exist
- **Unwired scripts** — any executable scripts in script directories without a Makefile target

### 4. Apply changes

- **Remove** all targets whose backing files, scripts, or tools don't exist
- **Fix** variables, paths, flags, and commands to match the real codebase
- **Add** new targets for discovered workflows
- **Update** `.PHONY`, the `help` text, and composite targets (`check`, `ci`, `all`) to stay consistent
- Preserve the existing section grouping style (e.g. `##@` comment headers)
- Keep target names idiomatic — use common conventions (`dev`, `build`, `test`, `lint`, `clean`)

### 5. Report a summary

After editing, output a concise changelog:

```
**Removed:** (list targets and why — missing script, missing tool, etc.)
**Fixed:** (list targets and what changed)
**Added:** (list new targets)
```
