"""Merchant endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from src.dependencies import get_merchant_service
from src.middleware.auth import AuthUser, get_current_user
from src.schemas.merchant import CreateMerchantRequest, MerchantResponse
from src.services.merchant_service import MerchantService

router = APIRouter(prefix="/merchants", tags=["Merchants"])


@router.get("", response_model=list[MerchantResponse])
async def list_merchants(
    tenant_id: str | None = Query(default=None, alias="tenantId"),
    actor: AuthUser = Depends(get_current_user),
    merchant_service: MerchantService = Depends(get_merchant_service),
) -> list[MerchantResponse]:
    merchants = await merchant_service.list_merchants(actor=actor, tenant_id=tenant_id)
    return [MerchantResponse.model_validate(item) for item in merchants]


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str,
    tenant_id: str | None = Query(default=None, alias="tenantId"),
    actor: AuthUser = Depends(get_current_user),
    merchant_service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    merchant = await merchant_service.get_merchant(
        actor=actor,
        tenant_id=tenant_id,
        merchant_id=merchant_id,
    )
    return MerchantResponse.model_validate(merchant)


@router.post("", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    payload: CreateMerchantRequest,
    actor: AuthUser = Depends(get_current_user),
    merchant_service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    merchant = await merchant_service.create_merchant(actor=actor, payload=payload)
    return MerchantResponse.model_validate(merchant)