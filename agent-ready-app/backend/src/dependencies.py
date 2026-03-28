"""FastAPI dependency injection container.

All dependencies are wired here. Routes use Depends() to inject them.
"""

from fastapi import Depends, Request

from src.cosmos.client import CosmosClientManager
from src.repositories.item import ItemRepository
from src.services.item_service import ItemService


def get_cosmos_manager(request: Request) -> CosmosClientManager:
    """Get the Cosmos DB client manager from app state."""
    manager: CosmosClientManager = request.app.state.cosmos_manager
    return manager


def get_item_repo(
    cosmos: CosmosClientManager = Depends(get_cosmos_manager),
) -> ItemRepository:
    """Get the item repository."""
    return ItemRepository(cosmos.database)


def get_item_service(
    item_repo: ItemRepository = Depends(get_item_repo),
) -> ItemService:
    """Get the item service."""
    return ItemService(item_repo)
