"""Audit event model stored in Cosmos DB."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    tenant_id: str = Field(alias="tenantId")
    event_id: str = Field(alias="eventId")
    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")
    action: str
    actor_id: str = Field(alias="actorId")
    occurred_at: str = Field(alias="occurredAt")
    details: dict[str, Any]