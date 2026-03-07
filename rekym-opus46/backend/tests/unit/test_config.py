"""Configuration tests."""

import pytest

from src.config import Settings


def test_default_settings() -> None:
    """Settings loads with sensible defaults."""
    settings = Settings(
        cosmos_endpoint="https://test.documents.azure.com:443/",
        _env_file=None,
    )
    assert settings.app_env == "development"
    assert settings.app_debug is True
    assert settings.cosmos_database == "myapp"


def test_production_blocks_debug() -> None:
    """APP_DEBUG=true is blocked in production."""
    with pytest.raises(ValueError, match="APP_DEBUG=true is not allowed in production"):
        Settings(
            cosmos_endpoint="https://test.documents.azure.com:443/",
            app_env="production",
            app_debug=True,
            auth_mode="header",
            _env_file=None,
        )


def test_production_blocks_disabled_auth() -> None:
    """AUTH_MODE=disabled is blocked in production."""
    with pytest.raises(ValueError, match="AUTH_MODE=disabled is not allowed in production"):
        Settings(
            cosmos_endpoint="https://test.documents.azure.com:443/",
            app_env="production",
            app_debug=False,
            auth_mode="disabled",
            _env_file=None,
        )


def test_key_mode_requires_key() -> None:
    """COSMOS_KEY is required when COSMOS_AUTH_MODE=key."""
    with pytest.raises(ValueError, match="COSMOS_KEY is required"):
        Settings(
            cosmos_endpoint="https://test.documents.azure.com:443/",
            cosmos_auth_mode="key",
            cosmos_key="",  # type: ignore[arg-type]
            _env_file=None,
        )
