"""Merchant domain model stored in Cosmos DB."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MerchantDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    tenant_id: str = Field(alias="tenantId")
    merchant_id: str = Field(alias="merchantId")
    legal_name: str = Field(alias="legalName")
    risk_tier: str = Field(alias="riskTier")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")