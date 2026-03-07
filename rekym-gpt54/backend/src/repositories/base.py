"""Shared async Cosmos repository helpers with 429 retry support."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from azure.cosmos.aio import ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosHttpResponseError


class BaseRepository:
    def __init__(self, database: DatabaseProxy, container_name: str) -> None:
        self._database = database
        self._container_name = container_name
        self._container: ContainerProxy | None = None

    @property
    def container(self) -> ContainerProxy:
        if self._container is None:
            self._container = self._database.get_container_client(self._container_name)
        return self._container

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        return await self._run_with_retry(lambda: self.container.create_item(body=item))

    async def upsert(self, item: dict[str, Any]) -> dict[str, Any]:
        return await self._run_with_retry(lambda: self.container.upsert_item(body=item))

    async def read(self, item_id: str, partition_key: str) -> dict[str, Any]:
        return await self._run_with_retry(
            lambda: self.container.read_item(item=item_id, partition_key=partition_key),
        )

    async def query(
        self,
        query_text: str,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
    ) -> list[dict[str, Any]]:
        async def _execute_query() -> list[dict[str, Any]]:
            kwargs: dict[str, Any] = {"query": query_text, "parameters": parameters or []}
            if partition_key is not None:
                kwargs["partition_key"] = partition_key

            items: list[dict[str, Any]] = []
            async for item in self.container.query_items(**kwargs):
                items.append(item)
            return items

        return await self._run_with_retry(_execute_query)

    async def _run_with_retry(self, operation: Any) -> Any:
        for attempt in range(3):
            try:
                return await operation()
            except CosmosHttpResponseError as exc:
                if exc.status_code != 429 or attempt == 2:
                    raise
                headers_attr: Any = getattr(exc, "headers", {})
                error_headers = cast(dict[str, Any], headers_attr)
                retry_after = float(error_headers.get("x-ms-retry-after-ms", 1000)) / 1000.0
                await asyncio.sleep(retry_after)
        raise RuntimeError("Retry loop exited unexpectedly")