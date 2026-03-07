"""Frontend telemetry intake schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FrontendErrorEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(min_length=1)
    source: str = Field(min_length=1)
    stack: str | None = None
    url: str | None = None
    correlation_id: str | None = Field(default=None, alias="correlationId")