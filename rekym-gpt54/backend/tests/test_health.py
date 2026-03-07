import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("COSMOS_ENDPOINT", "https://localhost:8081")
os.environ.setdefault(
    "COSMOS_KEY",
    "C2y6yDjf5/R+ob0N8A7Cgv30VRDj6eGkjc+1234567890abcdefghijklmnopqrstuv==",
)
os.environ.setdefault("COSMOS_AUTH_MODE", "key")
os.environ.setdefault("COSMOS_SSL_VERIFY", "false")
os.environ.setdefault("COSMOS_AUTO_CREATE_CONTAINERS", "false")

from src.main import app


@pytest.mark.asyncio
async def test_health_live_returns_alive() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}