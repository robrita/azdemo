"""Telemetry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.dependencies import get_telemetry_service
from src.schemas.telemetry import FrontendErrorEvent
from src.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("/frontend-errors", status_code=status.HTTP_202_ACCEPTED)
async def record_frontend_error(
    payload: FrontendErrorEvent,
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
) -> dict[str, str]:
    await telemetry_service.record_frontend_error(payload)
    return {"status": "accepted"}