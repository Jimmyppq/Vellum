from unittest.mock import AsyncMock, MagicMock
from app.core.registry import registry


def test_health_todos_ok(client, mock_adapter):
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["providers"]["mock"] == "ok"


def test_health_degraded(client):
    degraded_adapter = MagicMock()
    degraded_adapter.health = AsyncMock(return_value={"status": "error", "detail": "timeout"})
    registry.register("degraded", degraded_adapter)

    response = client.get("/v1/health")
    data = response.json()
    assert data["status"] == "degraded"
    assert "error" in data["providers"]["degraded"]


def test_health_sin_auth(client):
    from fastapi.testclient import TestClient
    from app.main import app
    no_auth_client = TestClient(app)
    response = no_auth_client.get("/v1/health")
    assert response.status_code == 200


def test_providers_lista(client):
    response = client.get("/v1/providers")
    assert response.status_code == 200
    data = response.json()
    assert any(p["name"] == "mock" for p in data)
