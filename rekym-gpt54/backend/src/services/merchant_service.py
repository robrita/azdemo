"""Merchant business logic service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from src.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.middleware.auth import AuthUser
from src.repositories.merchant import MerchantRepository
from src.schemas.merchant import CreateMerchantRequest
from src.services.audit_writer import AuditWriter


class MerchantService:
    def __init__(self, repository: MerchantRepository, audit_writer: AuditWriter) -> None:
        self._repository = repository
        self._audit_writer = audit_writer

    async def list_merchants(
        self,
        actor: AuthUser,
        tenant_id: str | None,
    ) -> list[dict[str, Any]]:
        effective_tenant_id = self._resolve_tenant(actor, tenant_id)
        return await self._repository.list_by_tenant(effective_tenant_id)

    async def get_merchant(
        self,
        actor: AuthUser,
        tenant_id: str | None,
        merchant_id: str,
    ) -> dict[str, Any]:
        effective_tenant_id = self._resolve_tenant(actor, tenant_id)
        document = await self._repository.get_by_merchant_id(effective_tenant_id, merchant_id)
        if document is None:
            raise NotFoundError(f"Merchant {merchant_id} was not found")
        return document

    async def create_merchant(self, actor: AuthUser, payload: CreateMerchantRequest) -> dict[str, Any]:
        effective_tenant_id = self._resolve_tenant(actor, payload.tenant_id)
        existing = await self._repository.get_by_merchant_id(effective_tenant_id, payload.merchant_id)
        if existing is not None:
            raise ConflictError(f"Merchant {payload.merchant_id} already exists in tenant {effective_tenant_id}")

        timestamp = datetime.now(UTC).isoformat()
        document: dict[str, Any] = {
            "id": f"merchant:{effective_tenant_id}:{payload.merchant_id}",
            "type": "merchant",
            "tenantId": effective_tenant_id,
            "merchantId": payload.merchant_id,
            "legalName": payload.legal_name,
            "riskTier": payload.risk_tier,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        created, _ = await asyncio.gather(
            self._repository.create(document),
            self._audit_writer.write_event(
                tenant_id=effective_tenant_id,
                entity_type="merchant",
                entity_id=payload.merchant_id,
                action="merchant_created",
                actor_id=actor.user_id,
                details={"legalName": payload.legal_name, "riskTier": payload.risk_tier},
            ),
        )
        return created

    def _resolve_tenant(self, actor: AuthUser, requested_tenant_id: str | None) -> str:
        if actor.role == "platform_admin":
            if requested_tenant_id is None:
                raise ForbiddenError("tenantId is required for platform administrators")
            return requested_tenant_id
        if requested_tenant_id is not None and requested_tenant_id != actor.tenant_id:
            raise ForbiddenError("Requested tenant does not match the authenticated tenant")
        return actor.tenant_id