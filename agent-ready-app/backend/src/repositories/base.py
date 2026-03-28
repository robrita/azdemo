"""Base async repository with CRUD, query, and count operations."""

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
            self._container = self._database.get_container_client(self._container_name)
        return self._container

    async def create(self, item: dict[str, Any]) -> dict[str, Any]:
        """Create a new item in the container."""
        return await self.container.create_item(body=item)

    async def read(self, item_id: str, partition_key: str) -> dict[str, Any]:
        """Read an item by ID and partition key."""
        return await self.container.read_item(item=item_id, partition_key=partition_key)

    async def upsert(self, item: dict[str, Any]) -> dict[str, Any]:
        """Upsert an item in the container."""
        return await self.container.upsert_item(body=item)

    async def delete(self, item_id: str, partition_key: str) -> None:
        """Delete an item by ID and partition key."""
        await self.container.delete_item(item=item_id, partition_key=partition_key)

    async def query(
        self,
        query_text: str,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | int | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a parameterized query and return all results."""
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
        """Execute a count query and return the scalar result."""
        results = await self.query(query_text, parameters, partition_key)
        first = results[0] if results else 0
        return int(first)  # type: ignore[arg-type]
