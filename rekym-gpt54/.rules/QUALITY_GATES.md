# Quality Gates

## Backend

- `make lint`
- `make format-check`
- `make typecheck`
- `make test`

## Frontend

- `make frontend-lint`
- `make frontend-build`
- `make frontend-test`

## Combined

- `make check`
- `make ci`

## Expectations

- Fix root causes instead of suppressing errors.
- Keep formatting, type checking, and tests green before considering a template change complete.
- Update the docs when changing the contract.