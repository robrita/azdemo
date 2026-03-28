"""Custom exceptions and global error handlers."""

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(AppError):
    """Duplicate or conflict error."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


class ForbiddenError(AppError):
    """Access denied by policy."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, status_code=403)


class ExternalServiceError(AppError):
    """External service failure."""

    def __init__(self, message: str = "External service error") -> None:
        super().__init__(message, status_code=502)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle application errors."""
    logger.warning(
        "Application error: %s (status=%d, path=%s)",
        exc.message,
        exc.status_code,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def _build_cosmos_error_detail(exc: Any) -> str:
    """Extract a safe error message from a Cosmos DB exception."""
    message = getattr(exc, "message", str(exc))
    status_code = getattr(exc, "status_code", 500)
    return f"Database error (status={status_code}): {message}"
