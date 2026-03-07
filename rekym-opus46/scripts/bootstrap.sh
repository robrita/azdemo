#!/usr/bin/env bash
# bootstrap.sh — One-command project setup
# Usage:  chmod +x scripts/bootstrap.sh && ./scripts/bootstrap.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "============================================"
echo "  Project Bootstrap"
echo "============================================"

# ---- .env file ----
if [ ! -f .env ]; then
  echo "→ Creating .env from .env.example..."
  cp .env.example .env
  echo "  ⚠  Edit .env with your Cosmos DB credentials before running."
else
  echo "→ .env already exists — skipping."
fi

# ---- Backend ----
echo ""
echo "── Backend ────────────────────────────────"
echo "→ Creating Python virtual environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Installing Python dependencies..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q

echo "→ Backend ready ✔"

# ---- Frontend ----
echo ""
echo "── Frontend ───────────────────────────────"
cd frontend

if [ ! -f .env ]; then
  echo "→ Creating frontend/.env from .env.example..."
  cp .env.example .env
fi

echo "→ Installing Node.js dependencies..."
npm ci --silent

echo "→ Frontend ready ✔"

cd "$ROOT_DIR"

# ---- Summary ----
echo ""
echo "============================================"
echo "  Setup Complete"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your Cosmos DB endpoint, key, and database name."
echo "  2. Start dev servers: make dev"
echo "     Or with Docker:   make docker-up"
echo "  3. Backend:  http://localhost:8000/api/v1/health"
echo "     Frontend: http://localhost:5173"
echo ""
