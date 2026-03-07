"""
Application configuration using pydantic-settings.

All configuration is loaded from environment variables with sensible defaults
for local development. See .rules/CONFIG_MANAGEMENT.md for conventions.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Cosmos DB
    # =========================================================================
    cosmos_endpoint: str = Field(
        default="",
        description="Cosmos DB account endpoint URL",
    )
    cosmos_database: str = Field(
        default="myapp",
        description="Cosmos DB database name",
    )
    cosmos_auth_mode: Literal["entra", "key"] = Field(
        default="entra",
        description="Auth mode: 'entra' (DefaultAzureCredential) or 'key' (account key)",
    )
    cosmos_key: SecretStr = Field(
        default=SecretStr(""),
        description="Cosmos DB account key (only used when cosmos_auth_mode='key')",
    )

    # =========================================================================
    # Auth
    # =========================================================================
    auth_mode: Literal["header", "disabled"] = Field(
        default="disabled",
        description="Authentication mode: 'header' or 'disabled'",
    )
    dev_persona: str = Field(
        default="admin",
        description="Development persona used when auth is bypassed",
    )

    # =========================================================================
    # App
    # =========================================================================
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    app_debug: bool = Field(
        default=True,
        description="Enable debug mode",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins",
    )

    # =========================================================================
    # Observability
    # =========================================================================
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR",
    )
    log_json: bool = Field(
        default=True,
        description="Emit structured JSON logs",
    )
    correlation_header_name: str = Field(
        default="X-Request-Id",
        description="Header name for correlation ID propagation",
    )
    application_insights_connection_string: str = Field(
        default="",
        description="Azure Application Insights connection string",
    )

    # =========================================================================
    # Startup Validation
    # =========================================================================
    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        """Block unsafe configurations in production."""
        if self.app_env == "production":
            if self.app_debug:
                msg = "APP_DEBUG=true is not allowed in production"
                raise ValueError(msg)
            if self.auth_mode == "disabled":
                msg = "AUTH_MODE=disabled is not allowed in production"
                raise ValueError(msg)
        if self.cosmos_auth_mode == "key" and not self.cosmos_key.get_secret_value():
            msg = "COSMOS_KEY is required when COSMOS_AUTH_MODE=key"
            raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return Settings()
