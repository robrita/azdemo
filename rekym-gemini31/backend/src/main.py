"""FastAPI app entry point with lifespan manager, CORS, exception handlers, router registration."""

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from src.config import get_settings
from src.cosmos.client import CosmosClientManager
from src.dependencies import get_rate_limit_service
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
from src.middleware.rate_limit import RateLimitMiddleware
from src.routes import (
    audit,
    health,
    partner_workflow,
    partner_workflow_admin,
    partners,
    telemetry,
    tracker,
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: register Cosmos DB manager (lazy init on first use)."""
    settings = get_settings()
    cosmos_manager = CosmosClientManager(settings)
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
    logger.info(
        "Application shutdown started",
        extra={
            "correlationId": "shutdown",
            "method": "-",
            "path": "lifespan",
            "status": 200,
            "durationMs": 0.0,
        },
    )
    await cosmos_manager.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)
    configure_application_insights(settings)

    application = FastAPI(
        title="GCash Re-KYM Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def observability_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_header_name = settings.correlation_header_name
        incoming_correlation_id = request.headers.get(correlation_header_name, "").strip()
        correlation_id = incoming_correlation_id or str(uuid.uuid4())

        context_token = set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response: Response | None = None

        try:
            response = await call_next(request)
            response.headers[correlation_header_name] = correlation_id
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            should_skip = request.url.path in {"/health", "/health/live", "/health/ready"}
            if not should_skip:
                status_code = response.status_code if response is not None else 500
                logger.info(
                    "HTTP request completed",
                    extra=build_log_extra(
                        correlation_id=correlation_id,
                        method=request.method,
                        path=request.url.path,
                        status=status_code,
                        duration_ms=duration_ms,
                    ),
                )
            reset_correlation_id(context_token)

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(
        RateLimitMiddleware,
        settings=settings,
        rate_limit_service=get_rate_limit_service(),
    )

    # Exception handlers
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(CosmosResourceNotFoundError, cosmos_not_found_handler)  # type: ignore[arg-type]
    application.add_exception_handler(CosmosHttpResponseError, cosmos_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)

    # Routers
    application.include_router(health.router, tags=["Health"])  # /health (no prefix)
    api = "/api/v1"
    application.include_router(audit.router, prefix=api)
    application.include_router(partners.router, prefix=api)
    application.include_router(partner_workflow.router, prefix=api)
    application.include_router(tracker.router, prefix=api)
    application.include_router(partner_workflow_admin.router, prefix=api)
    application.include_router(telemetry.router, prefix=api)

    # Serve frontend SPA
    if FRONTEND_DIR.is_dir():
        application.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

        @application.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            """Serve index.html for all non-API routes (SPA catch-all)."""
            if full_path.startswith(("api/", "health")):
                raise HTTPException(status_code=404, detail="Not found")
            file_path = FRONTEND_DIR / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")

    return application


app = create_app()
