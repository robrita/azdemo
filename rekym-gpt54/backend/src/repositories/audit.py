"""Audit event repository."""

from __future__ import annotations

from azure.cosmos.aio import DatabaseProxy

from src.repositories.base import BaseRepository


class AuditEventRepository(BaseRepository):
    def __init__(self, database: DatabaseProxy) -> None:
        super().__init__(database, "auditEvents")
