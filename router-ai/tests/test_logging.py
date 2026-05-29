def test_x_request_id_en_respuesta(client):
    response = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36  # UUID v4


def test_request_id_unico_por_solicitud(client):
    r1 = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "primera"}],
    })
    r2 = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "segunda"}],
    })
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
