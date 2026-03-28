"""Example item service — business logic layer."""

import uuid
from datetime import datetime, timezone
from typing import Any

from src.exceptions import NotFoundError
from src.repositories.item import ItemRepository


class ItemService:
    """Business logic for item operations."""

    def __init__(self, item_repo: ItemRepository) -> None:
        self._item_repo = item_repo

    async def list_items(self) -> list[dict[str, Any]]:
        """List all items."""
        return await self._item_repo.query("SELECT * FROM c ORDER BY c.createdAt DESC")

    async def get_item(self, item_id: str) -> dict[str, Any]:
        """Get a single item by ID."""
        results = await self._item_repo.query(
            "SELECT * FROM c WHERE c.id = @id",
            [{"name": "@id", "value": item_id}],
        )
        if not results:
            raise NotFoundError(f"Item {item_id} not found")
        return results[0]

    async def create_item(self, name: str, category: str) -> dict[str, Any]:
        """Create a new item."""
        now = datetime.now(timezone.utc).isoformat()
        item_doc: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "name": name,
            "category": category,
            "createdAt": now,
            "updatedAt": now,
        }
        return await self._item_repo.create(item_doc)
