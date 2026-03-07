# Tooling Overview

## Root workflow

Use root `make` targets as the primary workflow.

- `make install-dev`
- `make frontend-install`
- `make dev`
- `make frontend-dev`
- `make docker-up`
- `make check`
- `make ci`

## Bootstrap

Cross-platform bootstrap scripts are included under `scripts/`.

- `bootstrap.ps1` for Windows PowerShell.
- `bootstrap.sh` for Linux and macOS shells.

## CI

The included workflow installs backend and frontend dependencies and runs the template quality gates.