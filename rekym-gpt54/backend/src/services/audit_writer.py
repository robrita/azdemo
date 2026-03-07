"""Audit event writer service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from src.repositories.audit import AuditEventRepository


class AuditWriter:
    def __init__(self, repository: AuditEventRepository) -> None:
        self._repository = repository

    async def write_event(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        details: dict[str, Any],
    ) -> None:
        timestamp = datetime.now(UTC).isoformat()
        event_id = str(uuid.uuid4())
        document: dict[str, Any] = {
            "id": f"auditEvent:{event_id}",
            "type": "auditEvent",
            "tenantId": tenant_id,
            "eventId": event_id,
            "entityType": entity_type,
            "entityId": entity_id,
            "action": action,
            "actorId": actor_id,
            "occurredAt": timestamp,
            "details": details,
        }
        await self._repository.create(document)