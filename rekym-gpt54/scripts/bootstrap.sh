#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

if [ ! -f "local.settings.json" ]; then
  cp local.settings.example.json local.settings.json
fi

(cd frontend && npm install)

echo "Bootstrap complete. Activate the virtual environment, then run 'make dev' and 'make frontend-dev'."