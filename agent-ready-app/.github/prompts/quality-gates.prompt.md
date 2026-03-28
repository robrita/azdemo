---
description: "Run all mandatory quality gates on changed backend and frontend files using parallel sub-agents, fix every failure before reporting results"
agent: "agent"
---

# Quality Gates Prompt

## Purpose

Run all mandatory quality gates on changed **backend and frontend** files. **Use parallel sub-agents** to run backend and frontend gates simultaneously when both layers changed. Fix every failure before reporting results.

---

## Instructions

You are the **orchestrator**. You classify changes, dispatch parallel sub-agents, then run cross-cutting gates and produce the final report.

### Phase 1 — Identify Changed Files

Determine which files were added or modified in this session. Classify each as **backend** (`backend/`), **frontend** (`frontend/`), or **cross-cutting**. If unclear, ask.

### Phase 2 — Parallel Gate Execution via Sub-Agents

**When both backend and frontend files changed**, launch two sub-agents **in parallel** using `runSubagent`. Each sub-agent independently runs its layer's gates, fixes failures, and returns a structured report. This cuts wall-clock time roughly in half compared to sequential execution.

**When only one layer changed**, run that layer's gates directly — no sub-agent needed.

#### Sub-Agent: Backend Gates

Launch with description `"Backend quality gates"`. Include the full prompt below in the sub-agent's `prompt` parameter:

> You are running backend quality gates for a FastAPI + Cosmos DB project. The workspace root is the current directory. The Python virtualenv is already activated.
>
> Execute gates in **three internal phases**. Within each phase, run commands **in parallel using background terminals** where marked. For each failure: read the error, fix the root cause (never suppress with `# type: ignore`, `# noqa`, `# nosec` unless confirmed false positive with justification), then re-run the failed gate and all subsequent phases.
>
> **Phase A — Fix (sequential, modifies files):**
> These modify source files, so they must run sequentially before any checks.
> 1. `make lint-fix` — apply fixable Ruff violations
> 2. `make format` — apply formatting fixes
>
> **Phase B — Validate (parallel, all read-only):**
> After fixes are applied, these are all read-only and independent. Launch each as a **background terminal** (`isBackground: true`), then collect results from all four:
> 1. `make lint` — zero Ruff errors (confirms lint-fix was complete)
> 2. `make format-check` — all files already formatted (confirms format was complete)
> 3. `make typecheck` — zero mypy errors (strict mode)
> 4. `make security` — zero Bandit issues
>
> Wait for all four to finish and check each result. If any fail, fix the root cause, then re-run Phase A and Phase B.
>
> **Phase C — Test (parallel, all read-only):**
> Only proceed here after Phase B passes fully. Launch tests in parallel using background terminals:
> 1. `make test-unit` — all unit tests pass
> 2. `make test-contract` — all contract tests pass
> 3. `make test-integration` — all integration tests pass
>
> After all three pass, run `make test-cov` to verify ≥ 80% coverage target.
>
> After all phases complete, return EXACTLY this report (fill in results):
>
> ```
> BACKEND_REPORT_START
> | Gate | Result | Notes |
> |------|--------|-------|
> | Lint | PASS/FAIL | |
> | Format | PASS/FAIL | |
> | Type check | PASS/FAIL | |
> | Security | PASS/FAIL | |
> | Unit tests | PASS/FAIL | X passed, Y failed |
> | Contract tests | PASS/FAIL | |
> | Integration tests | PASS/FAIL | |
> | Coverage | PASS/FAIL | XX% (target: ≥ 80%) |
>
> Suppressions: (list with justifications, or "None")
> Pre-existing failures: (list, or "None")
> Files fixed: (list, or "None")
> BACKEND_REPORT_END
> ```

#### Sub-Agent: Frontend Gates

Launch with description `"Frontend quality gates"`. Include the full prompt below in the sub-agent's `prompt` parameter:

> You are running frontend quality gates for a React + TypeScript + Vite project. The workspace root is the current directory.
>
> Execute gates in **three internal phases**. Within each phase, run commands **in parallel using background terminals** where marked. For each failure: read the error, fix the root cause (never suppress with `// @ts-ignore`, `// eslint-disable` unless confirmed false positive with justification), then re-run the failed gate and all subsequent phases.
>
> **Phase A — Fix (sequential, modifies files):**
> 1. `make frontend-format` — apply Prettier formatting
>
> **Phase B — Validate (parallel, all read-only):**
> After formatting, these are independent and read-only. Launch each as a **background terminal** (`isBackground: true`), then collect results:
> 1. `make frontend-lint` — zero ESLint errors
> 2. `make frontend-build` — `tsc && vite build` succeeds, zero type errors
>
> Wait for both to finish. If any fail, fix the root cause, then re-run Phase A and Phase B.
>
> **Phase C — Test (parallel, all read-only):**
> Only proceed after Phase B passes. Launch in parallel:
> 1. `make frontend-test` — all Vitest tests pass
> 2. `make frontend-test-e2e` — all Playwright tests pass (when applicable)
>
> After all phases complete, return EXACTLY this report (fill in results):
>
> ```
> FRONTEND_REPORT_START
> | Gate | Result | Notes |
> |------|--------|-------|
> | Lint (ESLint) | PASS/FAIL | |
> | Format (Prettier) | PASS/FAIL | |
> | Build (tsc + vite) | PASS/FAIL | |
> | Unit tests (Vitest) | PASS/FAIL | X passed, Y failed |
> | E2E tests (Playwright) | PASS/FAIL/SKIPPED | |
>
> Suppressions: (list with justifications, or "None")
> Pre-existing failures: (list, or "None")
> Files fixed: (list, or "None")
> FRONTEND_REPORT_END
> ```

### Phase 3 — Cross-cutting Gates (After Sub-Agents Return)

Run these **after** both sub-agents complete, since pre-commit hooks touch files across layers and could conflict with fixes being applied by sub-agents.

| # | Gate | Command | Pass Criteria |
|---|------|---------|---------------|
| 1 | **Pre-commit hooks** | `make pre-commit-run` | All hooks pass on all files |

If pre-commit fails on files that a sub-agent just fixed, re-run the relevant layer's auto-fix commands (`make lint-fix && make format` or `make frontend-format`) and then re-run `make pre-commit-run`.

### Phase 4 — Manual Verification Checklist

After all automated gates pass, verify these items manually:

- [ ] **Dark mode compatibility** — UI renders correctly in both light and dark mode; `dark:` variants used for all hardcoded colors.
- [ ] **Theme compliance** — no hardcoded `blue-*` or `indigo-*` for brand/interactive colors; only `primary-*` tokens used. Component classes (`.btn-primary`, `.card`, etc.) used before custom Tailwind utilities.
- [ ] **API test cases parity** — `backend/api-tests.http` updated for any new, modified, or removed API endpoints.
- [ ] **Config parity** — any new/changed env vars reflected in `.env.example`, mirrored in local `.env`, and reflected in `local.settings.example.json` / `local.settings.json` when used by Azure Functions.
- [ ] **No secrets committed** — `.env`, connection strings, keys, and credentials are not in tracked files.
- [ ] **Cosmos DB field naming** — all document fields are camelCase; reserved words escaped with `c["field"]`; singleton config IDs use `"{type}:{key}"` format.
- [ ] **Badge/status tokens** — status, priority, and severity badges imported from `theme/tokens.ts`; no duplicate inline maps.

### Phase 5 — Consolidated Report

Merge the sub-agent reports into the final summary. Use this exact format:

```
## Quality Gates Report

### Backend

| Gate | Result | Notes |
|------|--------|-------|
| Lint | PASS/FAIL | (details if failed or suppressed) |
| Format | PASS/FAIL | |
| Type check | PASS/FAIL | |
| Security | PASS/FAIL | |
| Unit tests | PASS/FAIL | X passed, Y failed, Z errors |
| Contract tests | PASS/FAIL | |
| Integration tests | PASS/FAIL | |
| Coverage | PASS/FAIL | XX% (target: ≥ 80%) |

### Frontend

| Gate | Result | Notes |
|------|--------|-------|
| Lint (ESLint) | PASS/FAIL | |
| Format (Prettier) | PASS/FAIL | |
| Build (tsc + vite) | PASS/FAIL | |
| Unit tests (Vitest) | PASS/FAIL | X passed, Y failed |
| E2E tests (Playwright) | PASS/FAIL/SKIPPED | |

### Cross-cutting

| Gate | Result | Notes |
|------|--------|-------|
| Pre-commit hooks | PASS/FAIL | |

### Manual Checks

| Check | Result | Notes |
|-------|--------|-------|
| Dark mode | OK/NEEDS REVIEW | |
| Theme compliance | OK/NEEDS REVIEW | |
| API test cases parity | OK/NEEDS REVIEW | |
| Config parity | OK/N/A | |
| No secrets committed | OK/FAIL | |
| Cosmos DB naming | OK/N/A | |

**Changed files**: (list)
**Suppressions added**: (list with justifications, or "None")
**Pre-existing failures**: (list any failures unrelated to current changes, or "None")
```

---

## Suppression Rules

Suppressions (`# noqa`, `# type: ignore`, `# nosec`, `// @ts-ignore`, `// eslint-disable`) are allowed **only** when:

- The error is a confirmed false positive (e.g., a framework requires a parameter name that triggers unused-argument lint).
- You state the justification inline in the report.

**Never suppress to save time.** Fix the root cause.

## Distinguish Pre-existing vs. Introduced Failures

If a gate fails on code **not modified** in this session:

- Note it as **pre-existing** in the report.
- Do **not** fix unrelated failures unless asked.
- Do **not** let pre-existing failures block the report — clearly separate them.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Correct Behavior |
|--------------|------------------|
| Running backend then frontend sequentially when both changed | Use parallel sub-agents to run both simultaneously. |
| Running lint, typecheck, security sequentially after fixes | After fix phase, run all read-only checks in parallel via background terminals. |
| Running tests before validation passes | Only start tests after lint + format-check + typecheck + security all pass. |
| Skipping a gate because "it probably passes" | Run every gate. No exceptions. |
| Suppressing with `# type: ignore` / `// @ts-ignore` without justification | Fix the root cause or justify the suppression explicitly. |
| Reporting "all pass" without running commands | Show the actual command output or confirm execution. |
| Fixing pre-existing failures without being asked | Report them separately; only fix what you changed. |
| Running gates out of order within a layer | Follow the sequence: lint → format → typecheck → security → tests → coverage. |
| Running cross-cutting gates while sub-agents are still running | Wait for both sub-agents to finish first to avoid file conflicts. |
| Skipping frontend build gate | The build gate (`tsc && vite build`) is mandatory — it catches type errors. Never skip it. |
| Skipping manual verification | Automated gates are necessary but not sufficient. Always complete the manual checklist. |

---

## Execution Flow Summary

```
Phase 1: Identify changed files → classify backend / frontend / cross-cutting

Phase 2: PARALLEL (when both layers changed)
  ┌─ Sub-Agent A: Backend
  │   Phase A (sequential):  make lint-fix → make format
  │   Phase B (parallel):    make lint ║ make format-check ║ make typecheck ║ make security
  │   Phase C (parallel):    make test-unit ║ make test-contract ║ make test-integration
  │                          → make test-cov
  │
  └─ Sub-Agent B: Frontend
      Phase A (sequential):  make frontend-format
      Phase B (parallel):    make frontend-lint ║ make frontend-build
      Phase C (parallel):    make frontend-test ║ make frontend-test-e2e

Phase 3: Cross-cutting (after both sub-agents return)
  make pre-commit-run

Phase 4: Manual verification checklist

Phase 5: Merge sub-agent reports → produce consolidated report
```

Phase 5: Merge sub-agent reports → produce consolidated report
```

---

## Activation Phrase

When invoked, begin your response with:

> "Running quality gates on changed files. I will dispatch parallel sub-agents for backend and frontend gates, then run cross-cutting checks and produce a consolidated report."

Then execute the phases and produce the summary table.
