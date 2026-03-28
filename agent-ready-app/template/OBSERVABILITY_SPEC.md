# Observability & Logging Specification

> Portable reference for replicating this project's logging and telemetry setup in another FastAPI application.

---

## Table of Contents

1. [Overview](#overview)
2. [Dependencies](#dependencies)
3. [Configuration](#configuration)
4. [Structured Logging](#structured-logging)
   - [Log Formatters](#log-formatters)
   - [Request Context Propagation](#request-context-propagation)
   - [Logger Setup](#logger-setup)
5. [Distributed Tracing (OpenTelemetry)](#distributed-tracing-opentelemetry)
   - [Azure Monitor Export](#azure-monitor-export)
   - [FastAPI Instrumentation](#fastapi-instrumentation)
6. [Observability Middleware](#observability-middleware)
   - [Correlation ID Middleware](#correlation-id-middleware)
   - [Request Logging](#request-logging)
7. [Exception Handling](#exception-handling)
8. [Application Metrics](#application-metrics)
9. [Initialization Sequence](#initialization-sequence)
10. [Environment Variable Reference](#environment-variable-reference)
11. [Key Source Files](#key-source-files)
12. [Porting Checklist](#porting-checklist)

---

## Overview

The observability stack combines three pillars:

| Pillar | Implementation |
|--------|---------------|
| **Logging** | Python `logging` with structured JSON and colored-text formatters, request-scoped context injection |
| **Tracing** | OpenTelemetry SDK → Azure Monitor (Application Insights) export |
| **Metrics** | Lightweight in-process counter recorder; OpenTelemetry auto-instrumentation metrics |

All components are centralized in a single module (`src/lib/observability.py`) and wired via FastAPI middleware and lifespan hooks.

---

## Dependencies

Install these exact packages (pin versions in your own project):

```
azure-monitor-opentelemetry==1.8.6
opentelemetry-instrumentation-fastapi   # transitive via azure-monitor-opentelemetry
fastapi==0.129.2
pydantic-settings==2.13.1
```

The `azure-monitor-opentelemetry` meta-package bundles:
- `opentelemetry-sdk` (tracer, resource, span processors)
- `opentelemetry-api` (trace context API)
- `azure-monitor-opentelemetry-exporter` (Application Insights exporter)
- Auto-instrumentation for `requests`, `urllib3`, `logging`, etc.

---

## Configuration

All observability settings live in the centralized `Settings(BaseSettings)` class, loaded from environment variables. **Never use `os.getenv()` directly.**

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- Observability ---
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR",
    )
    log_json: bool = Field(
        default=True,
        description="Emit structured JSON logs (True) or colored plain text (False)",
    )
    correlation_header_name: str = Field(
        default="X-Request-Id",
        description="HTTP header used for correlation ID propagation",
    )
    applicationinsights_connection_string: SecretStr = Field(
        default=SecretStr(""),
        description="Azure Application Insights connection string",
    )
    app_env: str = Field(
        default="development",
        description="deployment.environment tag for telemetry resource",
    )
```

---

## Structured Logging

### Log Formatters

Two formatters are provided, selected by the `log_json` setting:

#### `JsonLogFormatter` — Production (structured JSON)

Every log record is serialized as a single-line JSON object:

```json
{
  "timestamp": "2026-03-16T12:00:00.000000+00:00",
  "level": "INFO",
  "logger": "src.services.public_upload_service",
  "message": "Public upload link resolved [abc-123]",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "traceId": "0af7651916cd43dd8448eb211c80319c",
  "spanId": "b7ad6b7169203331",
  "requestMethod": "POST",
  "requestPath": "/api/v1/upload/submit"
}
```

Fields appended on error: `exception` (formatted traceback), `stack` (stack info).

#### `ColoredLogFormatter` — Local development (plain text with ANSI colors)

```
14:32:01 INFO     src.main correlation=550e8400... HTTP POST /api/v1/upload/submit → 200 (42.3ms)
```

Level-based color mapping:

| Level | Color |
|-------|-------|
| DEBUG | Cyan `\033[36m` |
| INFO | Green `\033[32m` |
| WARNING | Yellow `\033[33m` |
| ERROR | Red `\033[31m` |
| CRITICAL | Bold Magenta `\033[1;35m` |

### Request Context Propagation

A `ContextVar`-based mechanism injects per-request metadata into every log record emitted during that request's lifetime, even across `await` boundaries.

**Data model:**

```python
@dataclass(frozen=True, slots=True)
class RequestContext:
    correlation_id: str   # From X-Request-Id header or auto-generated UUID
    method: str           # HTTP method (GET, POST, …)
    path: str             # Request path (/api/v1/…)
```

**Mechanism:**

1. `bind_request_context(...)` — called at the start of each request in middleware. Sets a `ContextVar` token.
2. `RequestContextFilter` — a `logging.Filter` attached to the root handler. Reads the `ContextVar` and injects `correlation_id`, `request_method`, `request_path`, `trace_id`, and `span_id` onto every `LogRecord`.
3. `clear_request_context(token)` — called in the middleware `finally` block to reset the context.

**Key code:**

```python
from contextvars import ContextVar, Token

_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)

def bind_request_context(*, correlation_id: str, method: str, path: str) -> Token:
    return _request_context.set(RequestContext(
        correlation_id=correlation_id, method=method, path=path,
    ))

def clear_request_context(token: Token) -> None:
    _request_context.reset(token)
```

**Filter implementation:**

```python
class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = _request_context.get()
        record.correlation_id = context.correlation_id if context else "-"
        record.request_method = context.method if context else "-"
        record.request_path = context.path if context else "-"

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            record.trace_id = f"{span_context.trace_id:032x}"
            record.span_id = f"{span_context.span_id:016x}"
        else:
            record.trace_id = "-"
            record.span_id = "-"
        return True
```

### Logger Setup

```python
OBSERVABILITY_HANDLER_NAME = "myapp-observability"
OBSERVABILITY_LOGGER_NAME = "src"

def configure_logging(settings: Settings) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Suppress verbose Azure SDK logs
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)

    handler = _get_or_create_observability_handler(root_logger)
    if settings.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(ColoredLogFormatter())
```

**Handler management:** A named handler (`"myapp-observability"`) is created once and reused. The `RequestContextFilter` is attached exactly once via `_ensure_request_context_filter()`.

**Per-module usage pattern:**

```python
import logging
logger = logging.getLogger(__name__)

# Then use standard logging calls:
logger.info("Upload completed upload_id=%s", upload_id)
logger.warning("Rate limit exceeded for IP %s", client_ip)
logger.exception("Unexpected error during blob upload")
```

Every module uses `logging.getLogger(__name__)` — the `RequestContextFilter` on the root handler automatically enriches all records.

---

## Distributed Tracing (OpenTelemetry)

### Azure Monitor Export

Azure Monitor export is configured when an Application Insights connection string is present:

```python
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.resources import Resource

def configure_azure_monitor_export(settings: Settings) -> None:
    global _azure_monitor_configured

    connection_string = settings.applicationinsights_connection_string.get_secret_value().strip()
    if not connection_string or _azure_monitor_configured:
        return

    configure_azure_monitor(
        connection_string=connection_string,
        logger_name=OBSERVABILITY_LOGGER_NAME,    # "src" — only export app logs
        resource=Resource.create({
            "service.name": "myapp-backend",
            "service.version": "0.1.0",
            "deployment.environment": settings.app_env,
        }),
        instrumentation_options={"fastapi": {"enabled": False}},  # we instrument manually
    )
    _azure_monitor_configured = True
```

**Key decisions:**
- `logger_name="src"` scopes log export to the application namespace only (avoids exporting noisy framework logs).
- `instrumentation_options={"fastapi": {"enabled": False}}` disables double-instrumentation — we call `FastAPIInstrumentor` separately for control over the app instance.
- A module-level `_azure_monitor_configured` guard prevents re-initialization.

### FastAPI Instrumentation

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def instrument_fastapi_app(app: FastAPI) -> None:
    app_id = id(app)
    if app_id in _instrumented_app_ids:
        return
    FastAPIInstrumentor.instrument_app(app)
    _instrumented_app_ids.add(app_id)
```

This creates automatic spans for every incoming HTTP request including:
- `http.method`, `http.url`, `http.status_code`
- `http.route` (FastAPI path template)
- Propagated W3C `traceparent` / `tracestate` headers

---

## Observability Middleware

### Correlation ID Middleware

Defined as inline `@application.middleware("http")` in `create_app()`:

```python
@application.middleware("http")
async def observability_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    # 1. Extract or generate correlation ID
    correlation_header = settings.correlation_header_name    # default: "X-Request-Id"
    incoming_id = request.headers.get(correlation_header, "").strip()
    correlation_id = incoming_id or str(uuid.uuid4())
    request.state.correlation_id = correlation_id

    # 2. Bind to ContextVar for structured logging
    token = bind_request_context(
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
    )

    start = time.perf_counter()
    response = None
    try:
        # 3. Stamp OpenTelemetry span with correlation ID
        current_span = trace.get_current_span()
        if current_span.get_span_context().is_valid:
            current_span.set_attribute("app.correlation_id", correlation_id)
            current_span.set_attribute("http.request.header.x_request_id", correlation_id)

        response = await call_next(request)
        response.headers[correlation_header] = correlation_id
        return response
    finally:
        # 4. Log the request (skip health endpoints)
        duration_ms = (time.perf_counter() - start) * 1000
        skip_paths = {"/health", "/health/live", "/health/ready"}
        if request.url.path not in skip_paths:
            status_code = response.status_code if response is not None else 500
            logger.info(
                "HTTP %s %s → %d (%.1fms) [%s]",
                request.method, request.url.path,
                status_code, duration_ms, correlation_id,
            )

        # 5. Clean up context
        clear_request_context(token)
```

**Behavior summary:**
- Incoming `X-Request-Id` header is honored; otherwise a new UUID is generated.
- The correlation ID is stored in `request.state`, the `ContextVar`, and the active OTel span.
- The correlation ID is echoed back in the response header.
- Health-check endpoints are excluded from access logging to reduce noise.

---

## Exception Handling

Centralized in `src/exceptions.py`. Two global handlers are registered:

```python
application.add_exception_handler(AppError, app_error_handler)
application.add_exception_handler(Exception, unhandled_exception_handler)
```

### `AppError` hierarchy

| Exception | Status | Use Case |
|-----------|--------|----------|
| `AppError` (base) | 500 | General application error |
| `NotFoundError` | 404 | Resource not found |
| `ConflictError` | 409 | Duplicate or conflict |
| `ForbiddenError` | 403 | Access denied |
| `ExternalServiceError` | 502 | External service failure |
| `BadRequestError` | 400 | Validation failure |
| `RateLimitError` | 429 | Rate limit exceeded (includes `Retry-After` header) |

### Handler logging behavior

```python
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "Application error: %s (status=%d, path=%s)",
        exc.message, exc.status_code, request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, **exc.extra_body},
        headers=exc.headers,
    )

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- **Known errors** (`AppError`) → `logger.warning()` — expected operational issues.
- **Unknown errors** → `logger.exception()` — includes full traceback for debugging.

---

## Application Metrics

A lightweight in-process counter (`src/lib/upload_metrics.py`):

```python
class UploadMetricsRecorder:
    def __init__(self) -> None:
        self._counters: Counter[str] = Counter()

    def increment(self, metric_name: str, tags: Mapping[str, str] | None = None) -> None:
        tag_suffix = ""
        if tags:
            parts = [f"{key}={value}" for key, value in sorted(tags.items())]
            tag_suffix = "|" + ",".join(parts)
        self._counters[f"{metric_name}{tag_suffix}"] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counters)
```

- Stored on `app.state.upload_metrics` and injected via FastAPI `Depends`.
- Useful for lightweight internal counters (e.g., upload success/failure rates).
- For production-grade metrics, OpenTelemetry auto-instrumentation captures HTTP metrics automatically via the Azure Monitor integration.

---

## Initialization Sequence

The observability system is initialized in a specific order inside `create_app()`:

```
1. get_settings()                          # Load configuration
2. FastAPI(title=..., lifespan=lifespan)   # Create app
3. configure_logging(settings)             # Set up root logger + formatters
4. configure_azure_monitor_export(settings)# Init OTel SDK + Azure exporter
5. instrument_fastapi_app(application)     # Attach OTel FastAPI spans
6. Register observability_middleware       # Correlation ID + request logging
7. Register exception handlers            # Structured error logging
```

Inside the `lifespan` context manager, `configure_logging(settings)` is called again to ensure the handler is set up even when the app is used via test clients.

### Azure Functions hosting

The app is hosted via Azure Functions ASGI adapter in `function_app.py`:

```python
from src.main import app as fastapi_app
app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
```

The entire observability stack works identically — it's wired to the FastAPI app, not the hosting layer.

---

## Environment Variable Reference

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `LOG_LEVEL` | `str` | `"INFO"` | Root logger level |
| `LOG_JSON` | `bool` | `true` | JSON logs (prod) vs colored text (dev) |
| `CORRELATION_HEADER_NAME` | `str` | `"X-Request-Id"` | HTTP header for correlation ID |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `SecretStr` | `""` | App Insights connection string (empty = disabled) |
| `APP_ENV` | `str` | `"development"` | `deployment.environment` resource tag |

---

## Key Source Files

| File | Responsibility |
|------|----------------|
| `backend/src/lib/observability.py` | All logging/tracing configuration, formatters, filters, context management |
| `backend/src/config.py` | `Settings(BaseSettings)` including observability fields |
| `backend/src/main.py` | `create_app()` — initialization sequence, middleware registration |
| `backend/src/exceptions.py` | Exception hierarchy and global error handlers with logging |
| `backend/src/lib/upload_metrics.py` | In-process counter-based metrics recorder |
| `backend/tests/unit/test_observability.py` | Unit tests for formatters, context filter, Azure Monitor config |

---

## Porting Checklist

To replicate this observability setup in a new FastAPI project:

1. **Install dependencies** — `azure-monitor-opentelemetry`, `pydantic-settings`
2. **Create `Settings` class** — add the five observability env vars from the reference table above
3. **Copy `observability.py`** — the module is self-contained; update `OBSERVABILITY_LOGGER_NAME` to match your project's root package name (e.g., `"src"` → `"myapp"`)
4. **Copy `upload_metrics.py`** — if you need in-process counters (optional)
5. **Wire in `create_app()`**:
   - Call `configure_logging(settings)` first
   - Call `configure_azure_monitor_export(settings)` second
   - Call `instrument_fastapi_app(app)` third
   - Register the observability middleware (correlation ID + request logging)
6. **Copy exception handlers** — register `AppError` and `Exception` handlers for structured error logging
7. **Use `logging.getLogger(__name__)` everywhere** — the root handler enriches all records automatically
8. **Suppress noisy loggers** — set `setLevel(WARNING)` on the `"azure"` and `"azure.core"` loggers to silence all Azure SDK noise
9. **Set `APPLICATIONINSIGHTS_CONNECTION_STRING`** in production — traces and logs are exported automatically
10. **Verify** — check JSON log output contains `correlationId`, `traceId`, `spanId` on every record
