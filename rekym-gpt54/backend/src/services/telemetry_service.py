"""Frontend telemetry ingestion service."""

from __future__ import annotations

import logging

from src.schemas.telemetry import FrontendErrorEvent

logger = logging.getLogger(__name__)


class TelemetryService:
    async def record_frontend_error(self, event: FrontendErrorEvent) -> None:
        logger.warning(
            "Frontend error received",
            extra={
                "correlationId": event.correlation_id or "frontend",
                "method": "POST",
                "path": "/api/v1/telemetry/frontend-errors",
                "status": 202,
                "durationMs": 0.0,
            },
        )
