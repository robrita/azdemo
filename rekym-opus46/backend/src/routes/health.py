"""Health check routes."""

import logging

from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    """Basic liveness check."""
    return {"status": "ok"}


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness probe — app is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(request: Request) -> dict[str, str]:
    """Readiness probe — checks Cosmos DB connectivity."""
    cosmos_manager = request.app.state.cosmos_manager
    is_ready = await cosmos_manager.ping()
    if not is_ready:
        logger.warning("Readiness probe failed: Cosmos DB unreachable")
        return {"status": "degraded", "cosmos": "unreachable"}
    return {"status": "ok"}
