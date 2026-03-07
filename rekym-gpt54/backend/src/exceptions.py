"""Typed application exceptions and centralized FastAPI handlers."""

from __future__ import annotations

import logging
from typing import Any

from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from fastapi import Request
from fastapi.responses import JSONResponse

from src.lib.observability import get_correlation_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 5) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ExternalServiceError(AppError):
    def __init__(self, message: str = "External service error") -> None:
        super().__init__(message, status_code=502)


def _log_context(request: Request, status_code: int) -> dict[str, Any]:
    return {
        "correlationId": getattr(request.state, "correlation_id", get_correlation_id()),
        "method": request.method,
        "path": request.url.path,
        "status": status_code,
        "durationMs": 0.0,
    }


def _headers(request: Request, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    settings = request.app.state.settings
    headers = dict(extra_headers or {})
    headers[settings.correlation_header_name] = getattr(
        request.state,
        "correlation_id",
        get_correlation_id(),
    )
    return headers


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitExceededError):
        headers["Retry-After"] = str(exc.retry_after)

    logger.warning("Application error emitted", extra=_log_context(request, exc.status_code))
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=_headers(request, headers),
    )


async def cosmos_not_found_handler(
    request: Request,
    _exc: CosmosResourceNotFoundError,
) -> JSONResponse:
    logger.warning("Cosmos resource not found", extra=_log_context(request, 404))
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"},
        headers=_headers(request),
    )


async def cosmos_error_handler(request: Request, exc: CosmosHttpResponseError) -> JSONResponse:
    if exc.status_code == 409:
        logger.warning("Cosmos conflict emitted", extra=_log_context(request, 409))
        return JSONResponse(
            status_code=409,
            content={"detail": "Resource conflict"},
            headers=_headers(request),
        )
    if exc.status_code == 429:
        logger.warning("Cosmos throttling emitted", extra=_log_context(request, 429))
        return JSONResponse(
            status_code=429,
            content={"detail": "Database rate limit exceeded"},
            headers=_headers(request, {"Retry-After": "5"}),
        )

    logger.error("Cosmos error emitted", extra=_log_context(request, 502))
    return JSONResponse(
        status_code=502,
        content={"detail": "Database error"},
        headers=_headers(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception",
        extra=_log_context(request, 500),
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_headers(request),
    )