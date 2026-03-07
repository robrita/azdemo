# Branching Strategy

## Branch Naming Convention

All feature branches must include the date of creation in `YYYY-MM-DD` format:

```
feature/<topic>-<YYYY-MM-DD>
```

**Examples:**
- `feature/branding-2026-02-21`
- `feature/auth-rework-2026-03-15`
- `feature/tickets-dataset-2026-01-10`

## Workflow: Merge & New Branch

When finishing a feature and starting new work:

```bash
# 1. Ensure working tree is clean
git status

# 2. Switch to main and pull latest
git checkout main
git pull origin main

# 3. Merge the completed feature branch
git merge feature/<completed-topic>-<date>

# 4. Push updated main
git push origin main

# 5. Create and push the new feature branch with today's date
git checkout -b feature/<new-topic>-<YYYY-MM-DD>
git push -u origin feature/<new-topic>-<YYYY-MM-DD>
```

## Rules

1. **Always include the date** — makes it easy to identify stale branches.
2. **Merge to main before branching** — new features start from an up-to-date main.
3. **Push with upstream tracking** — use `git push -u origin <branch>` on first push.
4. **Clean working tree** — commit or stash all changes before switching branches.
