"""Example item repository — extend BaseRepository for your domain."""

from typing import Any

from azure.cosmos.aio import DatabaseProxy

from src.repositories.base import BaseRepository


class ItemRepository(BaseRepository):
    """Repository for the 'items' Cosmos DB container."""

    def __init__(self, database: DatabaseProxy) -> None:
        super().__init__(database, "items")

    async def find_by_category(self, category: str) -> list[dict[str, Any]]:
        """Find items by category."""
        return await self.query(
            "SELECT * FROM c WHERE c.category = @category",
            [{"name": "@category", "value": category}],
        )
