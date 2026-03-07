"""Merchant request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CreateMerchantRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str = Field(alias="tenantId", min_length=1)
    merchant_id: str = Field(alias="merchantId", min_length=1)
    legal_name: str = Field(alias="legalName", min_length=1)
    risk_tier: str = Field(alias="riskTier", min_length=1)


class MerchantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    tenant_id: str = Field(alias="tenantId")
    merchant_id: str = Field(alias="merchantId")
    legal_name: str = Field(alias="legalName")
    risk_tier: str = Field(alias="riskTier")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")