"""Azure Functions v2 entrypoint — hosts the Re-KYM FastAPI app via ASGI."""

from __future__ import annotations

import sys
from pathlib import Path

import azure.functions as func

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.main import app as fastapi_app  # noqa: E402

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
