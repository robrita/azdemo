# Cosmos DB + Entra ID Authentication — Integration Spec

> **Purpose:** Portable reference for integrating Azure Cosmos DB (NoSQL) into a
> Python FastAPI application using Microsoft Entra ID (formerly Azure AD)
> passwordless authentication with a fallback to account-key auth for local
> development.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Python Dependencies](#3-python-dependencies)
4. [Configuration Layer](#4-configuration-layer)
5. [Cosmos Client Manager (Singleton)](#5-cosmos-client-manager-singleton)
6. [FastAPI Lifespan Integration](#6-fastapi-lifespan-integration)
7. [Dependency Injection](#7-dependency-injection)
8. [Repository Pattern](#8-repository-pattern)
9. [Pydantic Model Conventions](#9-pydantic-model-conventions)
10. [Database Provisioning Script](#10-database-provisioning-script)
11. [Indexing Policy Design](#11-indexing-policy-design)
12. [Environment Variable Reference](#12-environment-variable-reference)
13. [Azure RBAC Setup](#13-azure-rbac-setup)
14. [Docker Compose Configuration](#14-docker-compose-configuration)
15. [Health Check / Readiness Probe](#15-health-check--readiness-probe)
16. [Conventions & Gotchas](#16-conventions--gotchas)

---

## 1. Overview

This spec documents a production-proven pattern for connecting a **FastAPI**
(async, Python 3.12+) application to **Azure Cosmos DB NoSQL** using
**Microsoft Entra ID** (`DefaultAzureCredential`) as the primary auth
mechanism. An account-key fallback is provided for environments where Entra ID
is unavailable (e.g. CI pipelines, Cosmos DB Emulator).

**Key design decisions:**

| Decision | Rationale |
|---|---|
| `DefaultAzureCredential` (Entra ID) as default | No secrets to rotate; works with Managed Identity in Azure and `az login` locally |
| Account-key fallback via config toggle | Supports Cosmos Emulator and CI environments |
| Singleton `CosmosClientManager` | Single TCP connection pool per process; avoids per-request overhead |
| Lazy initialization | Client created on first access, not at import time |
| `BaseRepository` abstraction | DRY CRUD operations; easy to add new containers |
| camelCase document fields | Cosmos DB JSON convention; Pydantic aliases bridge Python snake_case |

### Architecture Layers

```
Route (FastAPI endpoint)
  └─▶ Service (business logic)
       └─▶ Repository (extends BaseRepository)
            └─▶ CosmosClientManager.database → ContainerProxy
                 └─▶ Azure Cosmos DB (Entra ID or key auth)
```

---

## 2. Prerequisites

| Requirement | Details |
|---|---|
| Python | ≥ 3.12 |
| Azure CLI | `az login` for local Entra ID auth |
| Azure Cosmos DB account | NoSQL API, serverless or provisioned |
| Azure RBAC | App identity needs `Cosmos DB Built-in Data Contributor` role |
| (Optional) Cosmos Emulator | For offline / key-auth development |

---

## 3. Python Dependencies

Pin exact versions in `pyproject.toml`:

```toml
[project]
dependencies = [
    "azure-cosmos==4.14.6",
    "azure-identity==1.25.1",
    "fastapi==0.129.2",
    "pydantic==2.12.5",
    "pydantic-settings==2.13.1",
]
```

| Package | Purpose |
|---|---|
| `azure-cosmos` | Async Cosmos DB SDK (`azure.cosmos.aio`) |
| `azure-identity` | `DefaultAzureCredential` for Entra ID tokens |
| `fastapi` | Web framework with async lifespan |
| `pydantic` | Domain models with camelCase aliases |
| `pydantic-settings` | Typed config from environment variables |

---

## 4. Configuration Layer

All environment variables are loaded through a single `Settings` class using
`pydantic-settings`. **Never use `os.getenv()` directly.**

```python
# src/config.py
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Cosmos DB ---
    cosmos_endpoint: str = Field(
        default="",
        description="Cosmos DB account endpoint URL",
    )
    cosmos_database: str = Field(
        default="myapp",
        description="Cosmos DB database name",
    )
    cosmos_auth_mode: Literal["entra", "key"] = Field(
        default="entra",
        description="Auth mode: 'entra' (DefaultAzureCredential) or 'key' (account key)",
    )
    cosmos_key: SecretStr = Field(
        default=SecretStr(""),
        description="Cosmos DB account key (only used when cosmos_auth_mode='key')",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

### Config behavior

| `COSMOS_AUTH_MODE` | Credential used | When to use |
|---|---|---|
| `entra` (default) | `DefaultAzureCredential()` | Production, staging, local dev with `az login` |
| `key` | `COSMOS_KEY` secret string | Cosmos Emulator, CI, environments without Entra |

---

## 5. Cosmos Client Manager (Singleton)

A singleton manager that lazily creates one `CosmosClient` and exposes a
`DatabaseProxy`. This class is the **only place** that touches
`CosmosClient` directly.

```python
# src/cosmos/client.py
import logging

from azure.cosmos.aio import CosmosClient, DatabaseProxy
from azure.identity.aio import DefaultAzureCredential

from src.config import Settings

logger = logging.getLogger(__name__)


class CosmosClientManager:
    """Manages a singleton async CosmosClient with lazy initialization."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: CosmosClient | None = None
        self._database: DatabaseProxy | None = None
        self._credential: DefaultAzureCredential | None = None

    def _ensure_initialized(self) -> None:
        """Lazily create the Cosmos client and database reference on first access."""
        if self._client is None:
            if self._settings.cosmos_auth_mode == "key":
                credential: str | DefaultAzureCredential = (
                    self._settings.cosmos_key.get_secret_value()
                )
            else:
                self._credential = DefaultAzureCredential()
                credential = self._credential
            self._client = CosmosClient(
                url=self._settings.cosmos_endpoint,
                credential=credential,
            )
            self._database = self._client.get_database_client(
                self._settings.cosmos_database
            )

    async def close(self) -> None:
        """Close the Cosmos client connection and credential."""
        if self._client:
            await self._client.close()
            self._client = None
            self._database = None
        if self._credential:
            await self._credential.close()
            self._credential = None

    @property
    def database(self) -> DatabaseProxy:
        """Return the database proxy, initializing lazily if needed."""
        self._ensure_initialized()
        return self._database  # type: ignore[return-value]

    async def ping(self) -> bool:
        """Check whether the configured Cosmos database is reachable."""
        try:
            database = self.database
            await database.read()
            return True
        except Exception:
            logger.exception("Cosmos readiness probe failed")
            return False
```

### Key design points

- **Lazy init:** `_ensure_initialized()` is called only when `.database` is
  first accessed — not during `__init__`.
- **Dual-credential:** A single `if/else` branch handles both Entra ID and
  account-key auth.
- **Graceful shutdown:** `close()` disposes both the `CosmosClient` and the
  `DefaultAzureCredential` (both hold async resources).
- **Readiness probe:** `ping()` does a `database.read()` to verify
  connectivity.

---

## 6. FastAPI Lifespan Integration

The `CosmosClientManager` is created during FastAPI's async lifespan context
and stored on `app.state`:

```python
# src/main.py (lifespan excerpt)
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from src.config import get_settings
from src.cosmos.client import CosmosClientManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    # --- Startup ---
    cosmos_manager = CosmosClientManager(settings)
    app.state.cosmos_manager = cosmos_manager
    app.state.settings = settings

    yield

    # --- Shutdown ---
    await cosmos_manager.close()


def create_app() -> FastAPI:
    return FastAPI(title="My App API", version="0.1.0", lifespan=lifespan)
```

**Lifecycle guarantees:**

| Phase | Action |
|---|---|
| Startup | `CosmosClientManager` instantiated (no network call yet) |
| First request | `_ensure_initialized()` opens TCP connection lazily |
| Shutdown (yield) | `cosmos_manager.close()` releases connections and credential |

---

## 7. Dependency Injection

FastAPI dependencies extract the singleton from `app.state` and pass it to
repositories:

```python
# src/dependencies.py
from fastapi import Depends, Request

from src.cosmos.client import CosmosClientManager
from src.repositories.upload import UploadRepository


def get_cosmos_manager(request: Request) -> CosmosClientManager:
    """Get the Cosmos DB client manager from app state."""
    return request.app.state.cosmos_manager


def get_upload_repo(
    cosmos: CosmosClientManager = Depends(get_cosmos_manager),
) -> UploadRepository:
    """Get the upload repository."""
    return UploadRepository(cosmos.database)
```

**Pattern:** Each repository dependency receives `cosmos.database`
(`DatabaseProxy`), never the raw `CosmosClient`.

---

## 8. Repository Pattern

### 8a. Base Repository

All container repositories extend `BaseRepository`, which provides generic
async CRUD and query methods:

```python
# src/repositories/base.py
from typing import Any

from azure.cosmos.aio import ContainerProxy, DatabaseProxy


class BaseRepository:
    """Generic Cosmos DB container operations."""

    def __init__(self, database: DatabaseProxy, container_name: str) -> None:
        self._container_name = container_name
        self._database = database
        self._container: ContainerProxy | None = None

    @property
    def container(self) -> ContainerProxy:
        if self._container is None:
            self._container = self._database.get_container_client(
                self._container_name
            )
        return self._container

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        return await self.container.create_item(body=item)

    async def read(self, item_id: str, partition_key: str | int) -> dict[str, Any]:
        return await self.container.read_item(
            item=item_id, partition_key=partition_key
        )

    async def upsert(self, item: dict[str, Any]) -> dict[str, Any]:
        return await self.container.upsert_item(body=item)

    async def delete(self, item_id: str, partition_key: str | int) -> None:
        await self.container.delete_item(
            item=item_id, partition_key=partition_key
        )

    async def query(
        self,
        query_text: str,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | int | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"query": query_text}
        if parameters:
            kwargs["parameters"] = parameters
        if partition_key is not None:
            kwargs["partition_key"] = partition_key

        items: list[dict[str, Any]] = []
        async for item in self.container.query_items(**kwargs):
            items.append(item)
        return items

    async def count(
        self,
        query_text: str = "SELECT VALUE COUNT(1) FROM c",
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | int | None = None,
    ) -> int:
        results = await self.query(query_text, parameters, partition_key)
        first = results[0] if results else 0
        return int(first)
```

### 8b. Concrete Repository Example

```python
# src/repositories/upload.py
from azure.cosmos.aio import DatabaseProxy

from src.repositories.base import BaseRepository


class UploadRepository(BaseRepository):
    def __init__(self, database: DatabaseProxy) -> None:
        super().__init__(database, "upload")  # container name

    async def get_upload_link(self, upload_id: str) -> ...:
        """Point-read by ID + partition key for efficiency."""
        item = await self.read(upload_id, partition_key=current_year)
        return ItemModel.model_validate(item)
```

**To add a new domain:**
1. Create a Pydantic model (`src/models/`)
2. Create a repository class extending `BaseRepository` (`src/repositories/`)
3. Add a dependency function in `src/dependencies.py`
4. Wire into the route via `Depends()`

---

## 9. Pydantic Model Conventions

All Cosmos DB documents use **camelCase** field names. Pydantic models use
snake_case Python attributes with camelCase aliases:

```python
from pydantic import BaseModel, ConfigDict, Field


class UploadLink(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    year_created: int = Field(alias="yearCreated")
    partner_id: str = Field(alias="partnerId")
    status: str = Field(alias="status")
    created_at: datetime | None = Field(default=None, alias="createdAt")
```

### Serialization to Cosmos DB

Always use `mode="json"` when dumping to a dict for Cosmos:

```python
# ✅ Correct — datetime → ISO 8601 string
doc = model.model_dump(by_alias=True, mode="json")
await repo.upsert(doc)

# ❌ Wrong — datetime stays as Python object, SDK raises TypeError
doc = model.model_dump(by_alias=True)
```

---

## 10. Database Provisioning Script

A standalone async script creates the database and containers idempotently:

```python
# scripts/provision_cosmos.py
import asyncio

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient, DatabaseProxy
from azure.identity.aio import DefaultAzureCredential

from src.config import get_settings

# Container definitions
UPLOAD_CONTAINER = "upload"
UPLOAD_PARTITION_KEY = PartitionKey(path="/yearCreated")
UPLOAD_INDEXING_POLICY = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [
        {"path": "/yearCreated/?"},
        {"path": "/partnerId/?"},
        {"path": "/status/?"},
        {"path": "/createdAt/?"},
    ],
    "excludedPaths": [
        {"path": "/*"},
        {"path": '/"_etag"/?'},
    ],
}


async def provision_cosmos() -> None:
    settings = get_settings()
    credential = None
    default_credential = None

    try:
        if settings.cosmos_auth_mode == "key":
            credential = settings.cosmos_key.get_secret_value()
        else:
            default_credential = DefaultAzureCredential()
            credential = default_credential

        client = CosmosClient(url=settings.cosmos_endpoint, credential=credential)
        async with client:
            database = await client.create_database_if_not_exists(
                id=settings.cosmos_database
            )
            await database.create_container_if_not_exists(
                id=UPLOAD_CONTAINER,
                partition_key=UPLOAD_PARTITION_KEY,
                indexing_policy=UPLOAD_INDEXING_POLICY,
            )
    finally:
        if default_credential is not None:
            await default_credential.close()


if __name__ == "__main__":
    asyncio.run(provision_cosmos())
```

**Usage:** `python -m scripts.provision_cosmos`

---

## 11. Indexing Policy Design

### Rules

1. Use **opt-out** strategy: exclude `/*`, then explicitly include queried paths.
2. **Never** include `/id/?` — Cosmos treats `id` as a system property; indexing
   it causes `BadRequest`.
3. Exclude large/nested fields: `/metadata/*`, `/pages/*`, `/fields/*`.
4. Always exclude `/"_etag"/?`.

### Example

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    { "path": "/yearCreated/?" },
    { "path": "/partnerId/?" },
    { "path": "/status/?" },
    { "path": "/createdAt/?" }
  ],
  "excludedPaths": [
    { "path": "/*" },
    { "path": "/metadata/*" },
    { "path": "/\"_etag\"/?" }
  ]
}
```

---

## 12. Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `COSMOS_ENDPOINT` | Yes | `""` | Cosmos DB account URL (`https://<account>.documents.azure.com:443/`) |
| `COSMOS_DATABASE` | Yes | `"myapp"` | Database name |
| `COSMOS_AUTH_MODE` | No | `"entra"` | `"entra"` for Entra ID or `"key"` for account key |
| `COSMOS_KEY` | Only if `key` mode | `""` | Account master key (keep in Key Vault in production) |

### Config file locations to update

When adding or changing a Cosmos DB config variable, update all of the following:

| File | Format |
|---|---|
| `.env.example` | `KEY=placeholder` |
| `.env` | `KEY=actual-value` |
| `local.settings.example.json` | `"KEY": "placeholder"` |
| `local.settings.json` | `"KEY": "actual-value"` |
| `local.env.json` | `[{"name": "KEY", "value": "..."}]` |
| `docker-compose.yaml` | `KEY: ${KEY:-default}` |
| `Settings` class in `src/config.py` | Pydantic field |

---

## 13. Azure RBAC Setup

### Entra ID (recommended for production)

The application identity (Managed Identity or developer principal) needs the
**Cosmos DB Built-in Data Contributor** role assigned at the Cosmos DB account
scope.

```bash
# Assign to a Managed Identity (e.g. Azure Functions system-assigned identity)
az cosmosdb sql role assignment create \
  --account-name <cosmos-account> \
  --resource-group <rg> \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --scope "/" \
  --principal-id <managed-identity-object-id>

# Assign to a developer (for local dev with `az login`)
az cosmosdb sql role assignment create \
  --account-name <cosmos-account> \
  --resource-group <rg> \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --scope "/" \
  --principal-id <your-aad-object-id>
```

### Built-in Cosmos DB data-plane roles

| Role Definition ID | Name | Permissions |
|---|---|---|
| `00000000-0000-0000-0000-000000000001` | Cosmos DB Built-in Data Reader | Read-only |
| `00000000-0000-0000-0000-000000000002` | Cosmos DB Built-in Data Contributor | Read + Write |

> **Note:** Standard Azure RBAC roles (e.g., `Cosmos DB Account Reader`) grant
> control-plane access only — they do NOT allow data operations. You must use
> the Cosmos DB Built-in Data roles above.

### DefaultAzureCredential chain (local dev)

When running locally, `DefaultAzureCredential` attempts credentials in order:

1. Environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`)
2. Workload Identity
3. Managed Identity
4. Azure CLI (`az login`)
5. Azure PowerShell
6. Azure Developer CLI (`azd auth login`)

For local development, simply run `az login` and ensure the signed-in user has
the Cosmos DB data-plane role assigned.

---

## 14. Docker Compose Configuration

Pass Cosmos config as environment variables:

```yaml
# docker-compose.yaml (excerpt)
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    environment:
      COSMOS_ENDPOINT: ${COSMOS_ENDPOINT:-}
      COSMOS_DATABASE: ${COSMOS_DATABASE:-myapp}
      COSMOS_AUTH_MODE: ${COSMOS_AUTH_MODE:-entra}
      COSMOS_KEY: ${COSMOS_KEY:-}
```

For containerized environments using Entra ID, the container must have access
to a credential source (Managed Identity, mounted Azure CLI config, or
environment-based service principal credentials).

---

## 15. Health Check / Readiness Probe

Use `CosmosClientManager.ping()` for Kubernetes or load-balancer health checks:

```python
# src/routes/health.py
from fastapi import APIRouter, Depends

from src.cosmos.client import CosmosClientManager
from src.dependencies import get_cosmos_manager

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz(
    cosmos: CosmosClientManager = Depends(get_cosmos_manager),
) -> dict:
    cosmos_ok = await cosmos.ping()
    return {
        "status": "healthy" if cosmos_ok else "degraded",
        "cosmos": "ok" if cosmos_ok else "unreachable",
    }
```

---

## 16. Conventions & Gotchas

### Do

- Use `async def` for all database operations (async SDK: `azure.cosmos.aio`)
- Always supply `partition_key` in point reads
- Use parameterized queries — never string-interpolate values
- Serialize Pydantic models with `model.model_dump(by_alias=True, mode="json")`
- Use singleton IDs like `"config:rate-limits"` for config documents
- Escape reserved words in queries: `c["status"]`, `c["key"]`, `c["type"]`
- Close the `DefaultAzureCredential` in the shutdown hook

### Don't

- Don't create `CosmosClient` per request
- Don't use `os.getenv()` directly — use `Settings(BaseSettings)`
- Don't add `/id/?` to indexing `includedPaths`
- Don't dump Pydantic models without `mode="json"` for Cosmos
- Don't use `c.[field]` syntax — use `c["field"]` for reserved words
- Don't use control-plane RBAC roles for data operations

---

## Quick-Start Checklist for a New App

1. **Install dependencies:**
   ```bash
   pip install azure-cosmos azure-identity pydantic pydantic-settings fastapi
   ```

2. **Copy the following source files** (adapt paths to your project):
   - `src/config.py` — Settings class with Cosmos config fields
   - `src/cosmos/client.py` — `CosmosClientManager`
   - `src/repositories/base.py` — `BaseRepository`
   - `src/dependencies.py` — FastAPI DI functions

3. **Set environment variables:**
   ```env
   COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
   COSMOS_DATABASE=myapp
   COSMOS_AUTH_MODE=entra
   ```

4. **Assign RBAC role** to your identity:
   ```bash
   az cosmosdb sql role assignment create \
     --account-name <account> --resource-group <rg> \
     --role-definition-id "00000000-0000-0000-0000-000000000002" \
     --scope "/" --principal-id <your-object-id>
   ```

5. **Run provisioning** (create database + containers):
   ```bash
   python -m scripts.provision_cosmos
   ```

6. **Wire lifespan** in your FastAPI app to create and close the manager.

7. **Add repositories** for each Cosmos container following the pattern.

8. **Verify** with the health endpoint: `GET /healthz`.
