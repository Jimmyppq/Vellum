import json


def test_stream_formato_sse(client):
    with client.stream("POST", "/v1/stream", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    }) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        raw = response.read().decode()

    lines = raw.strip().split("\n\n")
    events = [json.loads(line.removeprefix("data: ")) for line in lines if line.startswith("data: ")]

    assert any(e.get("delta") == "hola" for e in events)
    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) == 1
    assert done_events[0].get("usage") is not None


def test_stream_headers_sse(client):
    with client.stream("POST", "/v1/stream", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    }) as response:
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"
        assert response.headers.get("connection") == "keep-alive"
