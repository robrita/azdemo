"""Merchant repository."""

from __future__ import annotations

from typing import Any

from azure.cosmos.aio import DatabaseProxy

from src.repositories.base import BaseRepository


class MerchantRepository(BaseRepository):
    def __init__(self, database: DatabaseProxy) -> None:
        super().__init__(database, "merchants")

    async def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        query_text = (
            "SELECT * FROM c WHERE c[\"type\"] = @type AND c.tenantId = @tenantId "
            "ORDER BY c.createdAt DESC"
        )
        return await self.query(
            query_text,
            parameters=[
                {"name": "@type", "value": "merchant"},
                {"name": "@tenantId", "value": tenant_id},
            ],
            partition_key=tenant_id,
        )

    async def get_by_merchant_id(self, tenant_id: str, merchant_id: str) -> dict[str, Any] | None:
        query_text = (
            "SELECT TOP 1 * FROM c WHERE c[\"type\"] = @type AND c.tenantId = @tenantId "
            "AND c.merchantId = @merchantId"
        )
        results = await self.query(
            query_text,
            parameters=[
                {"name": "@type", "value": "merchant"},
                {"name": "@tenantId", "value": tenant_id},
                {"name": "@merchantId", "value": merchant_id},
            ],
            partition_key=tenant_id,
        )
        return results[0] if results else None