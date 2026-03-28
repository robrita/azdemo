"""Item routes — thin handlers that delegate to ItemService."""

from typing import Any

from fastapi import APIRouter, Depends

from src.dependencies import get_item_service
from src.schemas.item import CreateItemRequest
from src.services.item_service import ItemService

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("")
async def list_items(
    item_service: ItemService = Depends(get_item_service),
) -> list[dict[str, Any]]:
    """List all items."""
    return await item_service.list_items()


@router.get("/{item_id}")
async def get_item(
    item_id: str,
    item_service: ItemService = Depends(get_item_service),
) -> dict[str, Any]:
    """Get a single item by ID."""
    return await item_service.get_item(item_id)


@router.post("", status_code=201)
async def create_item(
    body: CreateItemRequest,
    item_service: ItemService = Depends(get_item_service),
) -> dict[str, Any]:
    """Create a new item."""
    return await item_service.create_item(name=body.name, category=body.category)
