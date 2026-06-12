"""Tests del contrato de error del circuit breaker: 503 PROVIDER_UNAVAILABLE
con Retry-After vs 422 PROVIDER_NOT_FOUND. Ver openspec/specs (llm-routing)."""
import time

import pytest

from app.core.circuit_breaker import CircuitBreaker
from app.core.errors import ProviderNotFound, ProviderUnavailable
from app.core.registry import registry


def _open_breaker(provider: str = "mock") -> None:
    breaker = registry._breakers[provider]
    for _ in range(breaker.failure_threshold):
        breaker.record_failure()
    assert breaker.state == "open"


# ---------------------------------------------------------------------------
# 3.1 Breaker abierto → 503 con Retry-After, sin invocar al adapter
# ---------------------------------------------------------------------------

def test_open_breaker_returns_503_with_retry_after(client, mock_adapter):
    _open_breaker()
    resp = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert resp.status_code == 503
    body = resp.json()["detail"]
    assert body["code"] == "PROVIDER_UNAVAILABLE"
    assert body["provider"] == "mock"
    assert body["retry_after_seconds"] >= 1
    assert resp.headers["Retry-After"] == str(body["retry_after_seconds"])
    mock_adapter.message.assert_not_called()


# ---------------------------------------------------------------------------
# 3.2 Regresión: proveedor inexistente sigue siendo 422
# ---------------------------------------------------------------------------

def test_unknown_provider_still_422(client):
    resp = client.post("/v1/message", json={
        "provider": "no-existe",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["code"] == "PROVIDER_NOT_FOUND"
    assert body.get("retry_after_seconds") is None


def test_registry_raises_typed_exceptions(client):
    with pytest.raises(ProviderNotFound):
        registry.get("no-existe")
    _open_breaker()
    with pytest.raises(ProviderUnavailable) as exc_info:
        registry.get("mock")
    assert 1 <= exc_info.value.retry_after_seconds <= 60


# ---------------------------------------------------------------------------
# 3.3 Half-open deja pasar; transición OPEN → HALF_OPEN tras el timeout
# ---------------------------------------------------------------------------

def test_half_open_lets_trial_call_through(client, mock_adapter):
    _open_breaker()
    # simular que ya venció el recovery_timeout
    registry._breakers["mock"]._opened_at = time.monotonic() - 61
    resp = client.post("/v1/message", json={
        "provider": "mock",
        "messages": [{"role": "user", "content": "Hola"}],
    })
    assert resp.status_code == 200
    assert registry._breakers["mock"].state in ("half_open", "closed")


def test_seconds_until_retry_decreases_with_time():
    breaker = CircuitBreaker(provider="x")
    for _ in range(breaker.failure_threshold):
        breaker.record_failure()
    assert breaker.state == "open"
    assert 1 <= breaker.seconds_until_retry() <= 60
    breaker._opened_at = time.monotonic() - 55
    assert breaker.seconds_until_retry() <= 5
    # nunca 0 mientras esté OPEN
    breaker._opened_at = time.monotonic() - 59.9
    assert breaker.seconds_until_retry() >= 1


def test_seconds_until_retry_zero_when_closed():
    breaker = CircuitBreaker(provider="x")
    assert breaker.seconds_until_retry() == 0


# ---------------------------------------------------------------------------
# 3.4 Mismo contrato en los tres endpoints
# ---------------------------------------------------------------------------

def test_same_503_contract_on_all_endpoints(client):
    _open_breaker()
    msg = {"provider": "mock", "messages": [{"role": "user", "content": "Hola"}]}

    for path, payload in (
        ("/v1/message", msg),
        ("/v1/stream", msg),
        ("/v1/embed", {"provider": "mock", "input": ["texto"]}),
    ):
        resp = client.post(path, json=payload)
        assert resp.status_code == 503, path
        assert resp.json()["detail"]["code"] == "PROVIDER_UNAVAILABLE", path
        assert "Retry-After" in resp.headers, path


# ---------------------------------------------------------------------------
# 3.5 /v1/providers refleja el estado del breaker; /v1/health no rompe
# ---------------------------------------------------------------------------

def test_providers_exposes_circuit_state(client):
    resp = client.get("/v1/providers")
    assert resp.status_code == 200
    entry = next(p for p in resp.json() if p["name"] == "mock")
    assert entry["circuit"] == "closed"

    _open_breaker()
    resp = client.get("/v1/providers")
    entry = next(p for p in resp.json() if p["name"] == "mock")
    assert entry["circuit"] == "open"


def test_health_works_with_open_breaker(client):
    _open_breaker()
    resp = client.get("/v1/health")
    assert resp.status_code == 200
