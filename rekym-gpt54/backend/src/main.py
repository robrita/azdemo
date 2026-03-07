"""FastAPI app entry point."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import RequestResponseEndpoint

from src.config import get_settings
from src.cosmos.client import CosmosClientManager
from src.exceptions import (
    AppError,
    app_error_handler,
    cosmos_error_handler,
    cosmos_not_found_handler,
    unhandled_exception_handler,
)
from src.lib.observability import (
    build_log_extra,
    configure_application_insights,
    configure_logging,
    reset_correlation_id,
    set_correlation_id,
)
from src.routes import health, merchants, telemetry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    cosmos_manager = CosmosClientManager(settings)
    await cosmos_manager.initialize()
    app.state.cosmos_manager = cosmos_manager
    app.state.settings = settings
    logger.info(
        "Application startup complete",
        extra={
            "correlationId": "startup",
            "method": "-",
            "path": "lifespan",
            "status": 200,
            "durationMs": 0.0,
        },
    )
    yield
    await cosmos_manager.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    configure_application_insights(settings)

    application = FastAPI(
        title="Template Merchant Hub API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def observability_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        incoming_correlation_id = request.headers.get(settings.correlation_header_name, "").strip()
        correlation_id = incoming_correlation_id or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        token = set_correlation_id(correlation_id)
        start = time.perf_counter()
        response: Response | None = None

        try:
            response = await call_next(request)
            response.headers[settings.correlation_header_name] = correlation_id
            return response
        finally:
            if request.url.path not in {"/health", "/health/live", "/health/ready"}:
                status_code = response.status_code if response is not None else 500
                logger.info(
                    "HTTP request completed",
                    extra=build_log_extra(
                        correlation_id=correlation_id,
                        method=request.method,
                        path=request.url.path,
                        status=status_code,
                        duration_ms=(time.perf_counter() - start) * 1000,
                    ),
                )
            reset_correlation_id(token)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(CosmosResourceNotFoundError, cosmos_not_found_handler)  # type: ignore[arg-type]
    application.add_exception_handler(CosmosHttpResponseError, cosmos_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)

    application.include_router(health.router)
    application.include_router(merchants.router, prefix="/api/v1")
    application.include_router(telemetry.router, prefix="/api/v1")
    return application


app = create_app()