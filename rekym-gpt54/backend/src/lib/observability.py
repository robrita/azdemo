"""Structured logging and correlation helpers."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from src.config import Settings

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    """Format logs as compact JSON records."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlationId": getattr(record, "correlationId", get_correlation_id()),
        }
        for key in ("method", "path", "status", "durationMs"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    """Configure root logging for the app process."""

    handler = logging.StreamHandler()
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)

    if not settings.log_include_uvicorn_access:
        logging.getLogger("uvicorn.access").disabled = True


def configure_application_insights(_settings: Settings) -> None:
    """Reserved hook for optional Application Insights wiring."""


def set_correlation_id(value: str) -> Token[str]:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[str]) -> None:
    _correlation_id.reset(token)


def get_correlation_id() -> str:
    return _correlation_id.get()


def build_log_extra(
    correlation_id: str,
    method: str,
    path: str,
    status: int,
    duration_ms: float,
) -> dict[str, Any]:
    return {
        "correlationId": correlation_id,
        "method": method,
        "path": path,
        "status": status,
        "durationMs": round(duration_ms, 2),
    }