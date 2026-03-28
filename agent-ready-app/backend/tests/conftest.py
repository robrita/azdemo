"""Test configuration and shared fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Return test settings."""
    return Settings(
        cosmos_endpoint="https://test.documents.azure.com:443/",
        cosmos_database="testdb",
        cosmos_auth_mode="key",
        cosmos_key="dGVzdC1rZXk=",  # type: ignore[arg-type]
        auth_mode="disabled",
        app_env="development",
    )


@pytest.fixture
def mock_cosmos_manager() -> MagicMock:
    """Return a mock CosmosClientManager."""
    manager = MagicMock()
    manager.database = MagicMock()
    manager.ping = AsyncMock(return_value=True)
    manager.close = AsyncMock()
    return manager


@pytest.fixture
def client(mock_cosmos_manager: MagicMock) -> TestClient:
    """Return a test client with mocked Cosmos DB."""
    app = create_app()
    app.state.cosmos_manager = mock_cosmos_manager
    app.state.settings = Settings(
        cosmos_endpoint="https://test.documents.azure.com:443/",
        cosmos_database="testdb",
        cosmos_auth_mode="key",
        cosmos_key="dGVzdC1rZXk=",  # type: ignore[arg-type]
        auth_mode="disabled",
        app_env="development",
    )
    return TestClient(app)
