---
description: "Run all mandatory quality gates on changed backend files, fix every failure before reporting results"
agent: "agent"
---

# Quality Gates Prompt

## Purpose

Run all mandatory quality gates on changed backend files. Fix every failure before reporting results. Reference project quality gate and checklist documentation where available.

---

## Instructions

You are validating code changes against the project's quality gates. Follow this procedure exactly.

### 1. Identify Changed Files

Determine which backend files were added or modified in this session. If unclear, ask.

### 2. Run All Gates — In Order

Execute each gate sequentially. **Do not skip any gate.** Report results as you go.

| # | Gate | Command | Pass Criteria |
|---|------|---------|---------------|
| 1 | **Lint** | `make lint` | Zero errors (Ruff) |
| 2 | **Format** | `make format-check` | All files already formatted |
| 3 | **Security** | `make security` | Zero issues (Bandit) |
| 4 | **Type check** | `make typecheck` | Zero errors (mypy) |
| 5 | **Tests** | `make test` | All tests pass |
| 6 | **Docs lint** | `make lint-docs` | AGENTS.md structure valid |

### 3. Fix Failures Immediately

For each failure:

1. **Read the error output** — understand the root cause before changing code.
2. **Fix the root cause** — do not suppress with `# type: ignore`, `# noqa`, or `# nosec` unless it is a confirmed false positive that you can justify.
3. **Re-run the failed gate** to confirm the fix.
4. **Re-run all subsequent gates** after any code fix (a lint fix may introduce a type error, etc.).

### 4. Suppression Rules

Suppressions (`# noqa`, `# type: ignore`, `# nosec`) are allowed **only** when:

- The error is a confirmed false positive (e.g., a framework requires a parameter name that triggers unused-argument lint).
- You state the justification inline in the report.

**Never suppress to save time.** Fix the root cause.

### 5. Report Results

After all gates pass, produce this summary table:

```
## Quality Gates Report

| Gate | Result | Notes |
|------|--------|-------|
| Lint | PASS/FAIL | (details if failed or suppressed) |
| Format | PASS/FAIL | |
| Security | PASS/FAIL | |
| Type check | PASS/FAIL | |
| Tests | PASS/FAIL | X passed, Y failed, Z errors |
| Docs lint | PASS/FAIL | |

**Changed files**: (list)
**Suppressions added**: (list with justifications, or "None")
**Pre-existing failures**: (list any failures unrelated to current changes, or "None")
```

### 6. Distinguish Pre-existing vs. Introduced Failures

If a gate fails on code **not modified** in this session:

- Note it as **pre-existing** in the report.
- Do **not** fix unrelated failures unless asked.
- Do **not** let pre-existing failures block the report — clearly separate them.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Correct Behavior |
|--------------|------------------|
| Skipping a gate because "it probably passes" | Run every gate. No exceptions. |
| Suppressing with `# type: ignore` without justification | Fix the root cause or justify the suppression explicitly. |
| Reporting "all pass" without running commands | Show the actual command output or confirm execution. |
| Fixing pre-existing failures without being asked | Report them separately; only fix what you changed. |
| Running gates out of order | Follow the sequence: lint → format → security → typecheck → tests → docs. |

---

## Activation Phrase

When invoked, begin your response with:

> "Running quality gates on changed files. I will execute each gate, fix any failures I introduced, and report results."

Then execute the gates in order and produce the summary table.
