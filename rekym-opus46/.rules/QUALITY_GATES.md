# Quality Gates

## Backend Gates (Mandatory)

After any backend change:

1. **Lint & format** — `make lint` and `make format-check`
2. **Security scan** — `make security` (Bandit)
3. **Type checking** — `make typecheck` (mypy, strict mode)
4. **Tests** — `make test` (unit → contract → integration)
5. **Coverage** — meet or exceed 80% target (`make test-cov`)

## Frontend Gates (Mandatory)

After any frontend change:

1. **Lint** — `make frontend-lint` (ESLint)
2. **Format** — `make frontend-format` (Prettier)
3. **Type check & Build** — `make frontend-build` (`tsc && vite build`)
4. **Unit tests** — `make frontend-test` (Vitest)

Quick combined: `make frontend-ci`

## Common Rules

- **Never** use `# type: ignore` to suppress errors — fix the root cause
- **Never** commit credentials, keys, or connection strings
- Build must succeed — no exceptions

## Cosmos DB SDK Type Workarounds

```python
# Use getattr() + cast() for partially unknown SDK attributes
headers_attr: Any = getattr(e, "headers", {})
error_headers = cast(dict[str, Any], headers_attr)
```
