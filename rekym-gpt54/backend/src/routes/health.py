"""Health probes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> Any:
    cosmos_ready = await request.app.state.cosmos_manager.ping()
    payload: dict[str, Any] = {
        "status": "healthy" if cosmos_ready else "degraded",
        "dependencies": {"cosmos": "up" if cosmos_ready else "down"},
    }
    if cosmos_ready:
        return payload

    logger.warning("Health check returned degraded state")
    return JSONResponse(status_code=503, content=payload)


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(request: Request) -> Any:
    cosmos_ready = await request.app.state.cosmos_manager.ping()
    if cosmos_ready:
        return {"status": "ready", "dependencies": {"cosmos": "up"}}

    logger.warning("Readiness check failed because Cosmos is unavailable")
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "dependencies": {"cosmos": "down"}},
    )