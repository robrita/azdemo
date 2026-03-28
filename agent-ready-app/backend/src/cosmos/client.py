"""Cosmos DB async singleton client manager with lifespan hooks."""

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
            self._database = self._client.get_database_client(self._settings.cosmos_database)

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
