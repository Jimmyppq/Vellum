"""Tests del store distribuido de rate limiting (RedisRateLimitStore) y de la
selección/degradación del store. Ver openspec/specs (router-ai-distributed-rate-limiting)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest

from app.core.rate_limit_store import (
    InMemoryRateLimitStore,
    RedisRateLimitStore,
)
from app.core.rate_limiter import RateLimiter


def _fake_redis(server=None):
    server = server or fakeredis.FakeServer()
    return fakeredis.FakeAsyncRedis(server=server), server


# ---------------------------------------------------------------------------
# 5.2 RedisRateLimitStore
# ---------------------------------------------------------------------------

async def test_increment_with_amount():
    client, _ = _fake_redis()
    store = RedisRateLimitStore(client)
    assert await store.increment("p:tpm", 60, amount=5000) == 5000
    assert await store.get_count("p:tpm", 60) == 5000


async def test_increment_accumulates_across_calls():
    client, _ = _fake_redis()
    store = RedisRateLimitStore(client)
    await store.increment("p:rpm", 60)
    await store.increment("p:rpm", 60)
    assert await store.get_count("p:rpm", 60) == 2


async def test_two_stores_share_counters():
    """Dos stores sobre el mismo Redis = dos réplicas compartiendo límite."""
    server = fakeredis.FakeServer()
    client_a, _ = _fake_redis(server)
    client_b, _ = _fake_redis(server)
    replica_a = RedisRateLimitStore(client_a)
    replica_b = RedisRateLimitStore(client_b)

    await replica_a.increment("openai:rpm", 60)
    await replica_b.increment("openai:rpm", 60)

    assert await replica_a.get_count("openai:rpm", 60) == 2
    assert await replica_b.get_count("openai:rpm", 60) == 2


async def test_sliding_window_expiry():
    """Con ventana de 1s, lo registrado deja de contar al salir de la ventana."""
    client, _ = _fake_redis()
    store = RedisRateLimitStore(client)
    await store.increment("p:rpm", 1)
    assert await store.get_count("p:rpm", 1) == 1
    await asyncio.sleep(1.1)
    assert await store.get_count("p:rpm", 1) == 0


async def test_seconds_until_oldest_expires():
    client, _ = _fake_redis()
    store = RedisRateLimitStore(client)
    assert await store.seconds_until_oldest_expires("vacio:rpm", 60) == 60
    await store.increment("p:rpm", 60)
    remaining = await store.seconds_until_oldest_expires("p:rpm", 60)
    assert 1 <= remaining <= 60


# ---------------------------------------------------------------------------
# 5.4 Fail-open: errores de Redis no bloquean solicitudes
# ---------------------------------------------------------------------------

def _broken_redis():
    client = MagicMock()
    client.mget = AsyncMock(side_effect=ConnectionError("redis caído"))
    pipeline = MagicMock()
    pipeline.__aenter__ = AsyncMock(side_effect=ConnectionError("redis caído"))
    pipeline.__aexit__ = AsyncMock(return_value=False)
    client.pipeline = MagicMock(return_value=pipeline)
    return client


async def test_store_fail_open_on_errors():
    store = RedisRateLimitStore(_broken_redis())
    assert await store.increment("p:rpm", 60) == 0
    assert await store.get_count("p:rpm", 60) == 0
    assert await store.seconds_until_oldest_expires("p:rpm", 60) == 1


async def test_limiter_allows_request_when_store_fails(tmp_path):
    config = tmp_path / "rate_limits.yaml"
    config.write_text("providers:\n  mock:\n    requests_per_minute: 1\n")
    limiter = RateLimiter(str(config), store=RedisRateLimitStore(_broken_redis()))
    result = await limiter.check_request("mock")
    assert result.allowed is True
    # record tampoco lanza
    await limiter.record_request("mock")


# ---------------------------------------------------------------------------
# 5.3 Selección por entorno y degradación en arranque
# ---------------------------------------------------------------------------

async def test_default_store_is_memory(monkeypatch):
    from app.core import config
    from app.main import _build_rate_limit_store

    monkeypatch.setattr(config.settings, "rate_limit_store", "memory")
    store, status = await _build_rate_limit_store()
    assert isinstance(store, InMemoryRateLimitStore)
    assert status == "memory"


async def test_redis_unreachable_degrades_to_memory(monkeypatch):
    from app.core import config
    from app.main import _build_rate_limit_store

    monkeypatch.setattr(config.settings, "rate_limit_store", "redis")
    monkeypatch.setattr(config.settings, "redis_url", "redis://127.0.0.1:1/0")
    store, status = await _build_rate_limit_store()
    assert isinstance(store, InMemoryRateLimitStore)
    assert status == "memory (degraded)"


# ---------------------------------------------------------------------------
# El RateLimiter completo funciona igual contra el store Redis
# ---------------------------------------------------------------------------

async def test_rate_limiter_with_redis_store_enforces_rpm(tmp_path):
    config = tmp_path / "rate_limits.yaml"
    config.write_text("providers:\n  mock:\n    requests_per_minute: 2\n")
    client, _ = _fake_redis()
    limiter = RateLimiter(str(config), store=RedisRateLimitStore(client))

    for _ in range(2):
        assert (await limiter.check_request("mock")).allowed
        await limiter.record_request("mock")

    result = await limiter.check_request("mock")
    assert result.allowed is False
    assert result.limit_type == "requests_per_minute"
    assert result.retry_after_seconds >= 1


async def test_record_tokens_single_operation(tmp_path):
    config = tmp_path / "rate_limits.yaml"
    config.write_text("providers:\n  mock:\n    tokens_per_minute: 6000\n")
    client, _ = _fake_redis()
    store = RedisRateLimitStore(client)
    limiter = RateLimiter(str(config), store=store)

    await limiter.record_tokens("mock", 5000)
    assert await store.get_count("mock:tpm", 60) == 5000
    result = await limiter.check_request("mock", estimated_tokens=1500)
    assert result.allowed is False
    assert result.limit_type == "tokens_per_minute"
