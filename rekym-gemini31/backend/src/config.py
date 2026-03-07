"""
Application configuration using pydantic-settings.

All configuration is loaded from environment variables with sensible defaults
for local development.

Security: Secrets use SecretStr to prevent accidental logging.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

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

    # =========================================================================
    # Cosmos DB
    # =========================================================================
    cosmos_endpoint: str = Field(
        default="",
        description="Cosmos DB account endpoint URL (e.g. https://<account>.documents.azure.com:443/)",
    )
    cosmos_database: str = Field(
        default="rekym",
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
    # Google Drive
    # =========================================================================
    google_drive_credentials_json: str = Field(
        default="",
        description="Google Drive service-account credentials JSON content",
    )
    google_drive_shared_drive_id: str = Field(
        default="",
        description="Google Drive shared drive ID",
    )

    # =========================================================================
    # SSO / Auth
    # =========================================================================
    sso_issuer: str = Field(
        default="",
        description="SSO token issuer URL",
    )
    sso_audience: str = Field(
        default="",
        description="SSO audience / client ID",
    )
    auth_mode: Literal["header", "disabled"] = Field(
        default="header",
        description=(
            "Authentication mode: 'header' for local header-based auth, 'disabled' for full bypass"
        ),
    )
    dev_persona: Literal[
        "admin",
        "compliance_officer",
        "account_manager",
        "maker",
        "checker",
        "supervisor",
        "scheduler",
    ] = Field(
        default="admin",
        description="Development persona used when auth is bypassed",
    )
    dev_user_id: str = Field(
        default="",
        description="Optional override for development user ID",
    )
    dev_user_roles: list[str] = Field(
        default_factory=list,
        description=(
            "Optional override for development user roles (comma-separated env string supported)"
        ),
    )

    # =========================================================================
    # Rate Limits
    # =========================================================================
    rate_limit_tenant_per_min: int = Field(
        default=120,
        description="Max requests per tenant per minute",
        ge=1,
    )
    rate_limit_tenant_per_hr: int = Field(
        default=3000,
        description="Max requests per tenant per hour",
        ge=1,
    )
    rate_limit_user_per_min: int = Field(
        default=30,
        description="Max requests per user per minute",
        ge=1,
    )
    rate_limit_user_per_hr: int = Field(
        default=600,
        description="Max requests per user per hour",
        ge=1,
    )

    # =========================================================================
    # MFA Lockout
    # =========================================================================
    mfa_max_attempts: int = Field(
        default=5,
        description="Max MFA attempts before lockout",
        ge=1,
    )
    mfa_lockout_minutes: int = Field(
        default=30,
        description="MFA lockout duration in minutes",
        ge=1,
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
    app_public_url: str = Field(
        default="http://localhost:5173",
        description="Public app URL used for email links",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins",
    )
    scheduler_static_key: SecretStr = Field(
        default=SecretStr(""),
        description="Static key for external scheduler nudge trigger",
    )
    log_level: str = Field(
        default="INFO",
        description="Application log level",
    )
    log_json: bool = Field(
        default=True,
        description="Emit logs in JSON format",
    )
    log_include_uvicorn_access: bool = Field(
        default=False,
        description="Include uvicorn access logs",
    )
    correlation_header_name: str = Field(
        default="X-Request-Id",
        description="Header name used for request correlation ID propagation",
    )
    application_insights_connection_string: SecretStr = Field(
        default=SecretStr(""),
        description="Azure Application Insights connection string",
    )

    # =========================================================================
    # Email (Azure Logic App)
    # =========================================================================
    email_logic_app_url: SecretStr = Field(
        default=SecretStr(""),
        description="Azure Logic App HTTP trigger URL for sending emails (contains SAS sig)",
    )
    webhook_email_secret: SecretStr = Field(
        default=SecretStr(""),
        description="Shared secret for inbound email webhook (X-Webhook-Secret)",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        """Accept comma-separated string or JSON array from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        """Normalize log level to uppercase string."""
        if isinstance(value, str):
            return value.strip().upper()
        return "INFO"

    @field_validator("dev_user_roles", mode="before")
    @classmethod
    def parse_dev_user_roles(cls, value: object) -> object:
        """Accept comma-separated role string or list for dev user roles."""
        if isinstance(value, str):
            return [role.strip() for role in value.split(",") if role.strip()]
        return value

    @model_validator(mode="after")
    def validate_config_consistency(self) -> Settings:
        """Fail fast on invalid or inconsistent configuration.

        Validates:
        - cosmos_endpoint must be set
        - cosmos_key is required when cosmos_auth_mode='key'
        - Production environments must not have auth disabled or debug on
        """
        if not self.cosmos_endpoint:
            raise ValueError(
                "COSMOS_ENDPOINT is required (e.g. https://<account>.documents.azure.com:443/)"
            )
        if self.cosmos_auth_mode == "key" and not self.cosmos_key.get_secret_value():
            raise ValueError("COSMOS_KEY is required when COSMOS_AUTH_MODE='key'")
        if self.app_env == "production":
            if self.auth_mode == "disabled":
                raise ValueError("AUTH_MODE='disabled' is not allowed in production")
            if self.app_debug:
                raise ValueError("APP_DEBUG=true is not allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings (singleton)."""
    return Settings()
