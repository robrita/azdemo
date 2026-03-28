---
description: "Run core quality gates (lint, format, typecheck, build, security, unit tests) on backend and frontend using parallel sub-agents, fix failures before reporting"
agent: "agent"
---

# Minimal Quality Gates

Run the six core quality gates on changed backend and frontend files. Use **parallel sub-agents** when both layers changed. Fix every failure before reporting.

---

## Phase 1 — Identify Changed Files

Classify changed files as **backend** (`backend/`) or **frontend** (`frontend/`).

## Phase 2 — Parallel Gate Execution

When **both** layers changed, launch two sub-agents **in parallel**. When only one layer changed, run that layer's gates directly.

### Sub-Agent: Backend Gates

Launch with description `"Backend minimal quality gates"`:

> You are running backend quality gates. The workspace root is the current directory. The Python virtualenv is already activated.
>
> Execute in three phases. Use **background terminals** for parallel steps.
>
> **Phase A — Fix (sequential):**
> 1. `make lint-fix` — apply fixable Ruff violations
> 2. `make format` — apply formatting
>
> **Phase B — Validate (parallel via background terminals):**
> 1. `make lint` — zero Ruff errors
> 2. `make format-check` — all files formatted
> 3. `make typecheck` — zero mypy errors
> 4. `make security` — zero Bandit issues
>
> If any fail, fix root cause, re-run Phase A and B.
>
> **Phase C — Test:**
> 1. `make test-unit` — all tests pass
>
> For each failure: read the error, fix the root cause (never suppress with `# type: ignore`, `# noqa`, `# nosec` unless confirmed false positive with justification), re-run the failed gate and subsequent phases.
>
> Return EXACTLY:
> ```
> BACKEND_REPORT_START
> | Gate | Result | Notes |
> |------|--------|-------|
> | Lint | PASS/FAIL | |
> | Format | PASS/FAIL | |
> | Type check | PASS/FAIL | |
> | Security | PASS/FAIL | |
> | Unit tests | PASS/FAIL | X passed, Y failed |
>
> Suppressions: (list with justifications, or "None")
> Pre-existing failures: (list, or "None")
> Files fixed: (list, or "None")
> BACKEND_REPORT_END
> ```

### Sub-Agent: Frontend Gates

Launch with description `"Frontend minimal quality gates"`:

> You are running frontend quality gates. The workspace root is the current directory.
>
> Execute in three phases. Use **background terminals** for parallel steps.
>
> **Phase A — Fix (sequential):**
> 1. `make frontend-format` — apply Prettier formatting
>
> **Phase B — Validate (parallel via background terminals):**
> 1. `make frontend-lint` — zero ESLint errors
> 2. `make frontend-build` — `tsc && vite build` succeeds
>
> If any fail, fix root cause, re-run Phase A and B.
>
> **Phase C — Test:**
> 1. `make frontend-test` — all Vitest tests pass
>
> For each failure: read the error, fix the root cause (never suppress with `// @ts-ignore`, `// eslint-disable` unless confirmed false positive with justification), re-run the failed gate and subsequent phases.
>
> Return EXACTLY:
> ```
> FRONTEND_REPORT_START
> | Gate | Result | Notes |
> |------|--------|-------|
> | Lint (ESLint) | PASS/FAIL | |
> | Format (Prettier) | PASS/FAIL | |
> | Build (tsc + vite) | PASS/FAIL | |
> | Unit tests (Vitest) | PASS/FAIL | X passed, Y failed |
>
> Suppressions: (list with justifications, or "None")
> Pre-existing failures: (list, or "None")
> Files fixed: (list, or "None")
> FRONTEND_REPORT_END
> ```

## Phase 3 — Report

Merge sub-agent reports into the final summary:

```
## Quality Gates Report (Minimal)

### Backend

| Gate | Result | Notes |
|------|--------|-------|
| Lint | PASS/FAIL | |
| Format | PASS/FAIL | |
| Type check | PASS/FAIL | |
| Security | PASS/FAIL | |
| Unit tests | PASS/FAIL | X passed, Y failed |

### Frontend

| Gate | Result | Notes |
|------|--------|-------|
| Lint (ESLint) | PASS/FAIL | |
| Format (Prettier) | PASS/FAIL | |
| Build (tsc + vite) | PASS/FAIL | |
| Unit tests (Vitest) | PASS/FAIL | X passed, Y failed |

**Changed files**: (list)
**Suppressions added**: (list with justifications, or "None")
**Pre-existing failures**: (list, or "None")
```

---

## Execution Flow

```
Phase 1: Identify changed files → classify backend / frontend

Phase 2: PARALLEL (when both layers changed)
  ┌─ Sub-Agent A: Backend
  │   Fix (sequential):      make lint-fix → make format
  │   Validate (parallel):   make lint ║ make format-check ║ make typecheck ║ make security
  │   Test:                  make test-unit
  │
  └─ Sub-Agent B: Frontend
      Fix (sequential):      make frontend-format
      Validate (parallel):   make frontend-lint ║ make frontend-build
      Test:                  make frontend-test

Phase 3: Merge reports → consolidated summary
```
