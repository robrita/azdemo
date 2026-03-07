"""Async singleton Cosmos DB client manager with optional local bootstrap."""

from __future__ import annotations

import logging

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient, DatabaseProxy
from azure.identity.aio import DefaultAzureCredential

from src.config import Settings

logger = logging.getLogger(__name__)


class CosmosClientManager:
    """Create and manage one async Cosmos client per process."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: CosmosClient | None = None
        self._credential: DefaultAzureCredential | None = None
        self._database: DatabaseProxy | None = None

    async def initialize(self) -> None:
        if self._client is not None:
            return

        if self._settings.cosmos_auth_mode == "key":
            credential: str | DefaultAzureCredential = self._settings.cosmos_key.get_secret_value()
        else:
            self._credential = DefaultAzureCredential()
            credential = self._credential

        self._client = CosmosClient(
            url=self._settings.cosmos_endpoint,
            credential=credential,
            connection_verify=self._settings.cosmos_ssl_verify,
        )

        if self._settings.cosmos_auto_create_containers:
            self._database = await self._client.create_database_if_not_exists(
                id=self._settings.cosmos_database,
            )
            await self._database.create_container_if_not_exists(
                id="merchants",
                partition_key=PartitionKey(path="/tenantId"),
            )
            await self._database.create_container_if_not_exists(
                id="auditEvents",
                partition_key=PartitionKey(path="/tenantId"),
            )
        else:
            self._database = self._client.get_database_client(self._settings.cosmos_database)

        logger.info("Cosmos client initialized")

    @property
    def database(self) -> DatabaseProxy:
        if self._database is None:
            raise RuntimeError("Cosmos client accessed before initialization")
        return self._database

    async def ping(self) -> bool:
        try:
            await self.database.read()
            return True
        except Exception:
            logger.exception("Cosmos readiness probe failed")
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._database = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None