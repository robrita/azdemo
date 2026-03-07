"""Pydantic schemas for item request/response validation."""

from pydantic import BaseModel, Field


class CreateItemRequest(BaseModel):
    """Request body for creating an item."""

    name: str = Field(min_length=1, max_length=200, description="Item name")
    category: str = Field(min_length=1, max_length=100, description="Item category")
