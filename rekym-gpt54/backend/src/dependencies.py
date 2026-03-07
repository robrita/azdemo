"""Centralized FastAPI dependency providers."""

from __future__ import annotations

from fastapi import Depends, Request

from src.cosmos.client import CosmosClientManager
from src.repositories.audit import AuditEventRepository
from src.repositories.merchant import MerchantRepository
from src.services.audit_writer import AuditWriter
from src.services.merchant_service import MerchantService
from src.services.telemetry_service import TelemetryService


def get_cosmos_manager(request: Request) -> CosmosClientManager:
    manager: CosmosClientManager = request.app.state.cosmos_manager
    return manager


def get_merchant_repository(
    cosmos_manager: CosmosClientManager = Depends(get_cosmos_manager),
) -> MerchantRepository:
    return MerchantRepository(cosmos_manager.database)


def get_audit_repository(
    cosmos_manager: CosmosClientManager = Depends(get_cosmos_manager),
) -> AuditEventRepository:
    return AuditEventRepository(cosmos_manager.database)


def get_audit_writer(
    repository: AuditEventRepository = Depends(get_audit_repository),
) -> AuditWriter:
    return AuditWriter(repository)


def get_merchant_service(
    repository: MerchantRepository = Depends(get_merchant_repository),
    audit_writer: AuditWriter = Depends(get_audit_writer),
) -> MerchantService:
    return MerchantService(repository, audit_writer)


def get_telemetry_service() -> TelemetryService:
    return TelemetryService()