"""Item service tests."""

from unittest.mock import AsyncMock

import pytest

from src.exceptions import NotFoundError
from src.services.item_service import ItemService


@pytest.fixture
def mock_item_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def item_service(mock_item_repo: AsyncMock) -> ItemService:
    return ItemService(mock_item_repo)


async def test_list_items(item_service: ItemService, mock_item_repo: AsyncMock) -> None:
    """list_items returns items from repo."""
    mock_item_repo.query.return_value = [{"id": "1", "name": "Test"}]
    result = await item_service.list_items()
    assert len(result) == 1
    assert result[0]["name"] == "Test"


async def test_get_item_found(item_service: ItemService, mock_item_repo: AsyncMock) -> None:
    """get_item returns the item when it exists."""
    mock_item_repo.query.return_value = [{"id": "1", "name": "Test"}]
    result = await item_service.get_item("1")
    assert result["id"] == "1"


async def test_get_item_not_found(item_service: ItemService, mock_item_repo: AsyncMock) -> None:
    """get_item raises NotFoundError when item doesn't exist."""
    mock_item_repo.query.return_value = []
    with pytest.raises(NotFoundError, match="Item .* not found"):
        await item_service.get_item("nonexistent")


async def test_create_item(item_service: ItemService, mock_item_repo: AsyncMock) -> None:
    """create_item delegates to repo and returns the created item."""
    mock_item_repo.create.return_value = {"id": "new-id", "name": "New", "category": "test"}
    result = await item_service.create_item(name="New", category="test")
    assert result["name"] == "New"
    mock_item_repo.create.assert_called_once()
