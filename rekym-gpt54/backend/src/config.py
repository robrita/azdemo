"""Centralized application settings loaded from root environment files."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    cosmos_endpoint: str = Field(default="")
    cosmos_database: str = Field(default="templateapp")
    cosmos_auth_mode: Literal["entra", "key"] = Field(default="key")
    cosmos_key: SecretStr = Field(default=SecretStr(""))
    cosmos_ssl_verify: bool = Field(default=False)
    cosmos_auto_create_containers: bool = Field(default=True)

    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_debug: bool = Field(default=True)
    app_public_url: str = Field(default="http://localhost:5173")
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    auth_mode: Literal["header", "disabled"] = Field(default="disabled")
    dev_persona: str = Field(default="platform_admin")
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    log_include_uvicorn_access: bool = Field(default=False)
    correlation_header_name: str = Field(default="X-Request-Id")
    application_insights_connection_string: SecretStr = Field(default=SecretStr(""))

    partner_api_base_url: str = Field(default="")
    partner_api_timeout_seconds: int = Field(default=15, ge=1, le=120)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.strip("[]").replace('"', "").split(",") if item.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
        return "INFO"

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        if not self.cosmos_endpoint:
            raise ValueError("COSMOS_ENDPOINT is required")
        if self.cosmos_auth_mode == "key" and not self.cosmos_key.get_secret_value():
            raise ValueError("COSMOS_KEY is required when COSMOS_AUTH_MODE=key")
        if self.app_env == "production":
            if self.auth_mode == "disabled":
                raise ValueError("AUTH_MODE=disabled is not allowed in production")
            if self.app_debug:
                raise ValueError("APP_DEBUG=true is not allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()