"""FastAPI app entry point with lifespan manager, CORS, exception handlers, and router registration."""

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import RequestResponseEndpoint

from src.config import get_settings
from src.cosmos.client import CosmosClientManager
from src.exceptions import AppError, app_error_handler, unhandled_exception_handler
from src.routes import health, items

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize Cosmos DB manager, validate config."""
    settings = get_settings()
    cosmos_manager = CosmosClientManager(settings)
    app.state.cosmos_manager = cosmos_manager
    app.state.settings = settings

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown started")
    await cosmos_manager.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="My App API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Observability middleware: correlation ID + request logging
    @application.middleware("http")
    async def observability_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_header = settings.correlation_header_name
        incoming_id = request.headers.get(correlation_header, "").strip()
        correlation_id = incoming_id or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            response.headers[correlation_header] = correlation_id
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            skip_paths = {"/health", "/health/live", "/health/ready"}
            if request.url.path not in skip_paths:
                status_code = response.status_code if response is not None else 500
                logger.info(
                    "HTTP %s %s → %d (%.1fms) [%s]",
                    request.method,
                    request.url.path,
                    status_code,
                    duration_ms,
                    correlation_id,
                )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)

    # Routers
    application.include_router(health.router, tags=["Health"])
    application.include_router(items.router, prefix="/api/v1")

    return application


app = create_app()
