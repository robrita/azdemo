# Execution Plans

This directory contains versioned execution plans for complex, multi-step work.

## Directory Structure

```
exec-plans/
├── README.md          ← this file
├── active/            ← plans currently in progress
└── completed/         ← plans that have been finished
```

## When to Create a Plan

Create an execution plan when:
- A task spans multiple files, domains, or sessions
- The scope is ambiguous and needs to be broken down before starting
- Coordination or sequencing between steps matters
- You want a checkpoint that survives context loss

## Plan Format

Each plan is a markdown file named `YYYY-MM-DD-short-description.md`. Example:

```markdown
# Plan: Short Description

## Goal
One-sentence objective.

## Steps
1. [ ] Step one — description
2. [ ] Step two — description
3. [ ] Step three — description

## Decisions
- Decision A: rationale
- Decision B: rationale

## Progress Log
- 2026-02-17: Created plan, completed steps 1–2
- 2026-02-18: Step 3 done, moved to completed/
```

## Lifecycle

1. Create the plan in `active/`
2. Update progress and check off steps as work proceeds
3. When fully done, move to `completed/`

Plans are versioned artifacts — commit them alongside the code they describe.
