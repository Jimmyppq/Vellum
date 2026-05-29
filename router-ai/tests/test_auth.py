from fastapi.testclient import TestClient
from app.main import app

API_KEY = "test-key-123"


def test_sin_api_key_retorna_401():
    with TestClient(app) as c:
        response = c.post("/v1/message", json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "Hola"}],
        })
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert "requerido" in response.json()["message"]


def test_api_key_invalida_retorna_401():
    with TestClient(app, headers={"X-API-Key": "clave-incorrecta"}) as c:
        response = c.post("/v1/message", json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "Hola"}],
        })
    assert response.status_code == 401
    assert "inválida" in response.json()["message"]


def test_api_key_valida_pasa(client):
    response = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 200


def test_health_no_requiere_auth():
    with TestClient(app) as c:
        response = c.get("/v1/health")
    assert response.status_code == 200
