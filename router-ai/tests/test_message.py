import pytest


def test_message_exitoso(client):
    response = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "request_id" in body["meta"]
    data = body["data"]
    assert data["provider"] == "mock"
    assert data["content"] == "respuesta de prueba"
    assert "usage" in data


def test_message_proveedor_no_registrado(client):
    response = client.post("/v1/message", json={
        "provider": "no-existe",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROVIDER_NOT_FOUND"


def test_message_sin_provider(client):
    response = client.post("/v1/message", json={
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 422


def test_message_error_proveedor(client, mock_adapter):
    mock_adapter.message.side_effect = RuntimeError("API error 500")
    response = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "PROVIDER_ERROR"
