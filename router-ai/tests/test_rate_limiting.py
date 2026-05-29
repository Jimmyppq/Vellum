import pytest
from app.middleware.rate_limit import set_limiter
from app.core.rate_limiter import RateLimiter
from app.core.rate_limit_store import InMemoryRateLimitStore


@pytest.fixture
def strict_limiter(tmp_path):
    config = tmp_path / "rate_limits.yaml"
    config.write_text(
        "providers:\n  mock:\n    requests_per_minute: 2\n    tokens_per_minute: null\n"
    )
    store = InMemoryRateLimitStore()
    limiter = RateLimiter(str(config), store=store)
    set_limiter(limiter)
    yield limiter
    set_limiter(None)


def test_dentro_del_limite(client, strict_limiter):
    response = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 200
    assert "X-RateLimit-Remaining-RPM" in response.headers


def test_supera_limite_rpm(client, strict_limiter):
    for _ in range(2):
        client.post("/v1/message", json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "Hola"}],
        })
    response = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert response.status_code == 429
    data = response.json()
    assert data["code"] == "RATE_LIMIT_EXCEEDED"
    assert data["limit_type"] == "requests_per_minute"
    assert "retry_after_seconds" in data
