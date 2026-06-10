import pytest


@pytest.mark.asyncio
async def test_set_and_get_config(client):
    resp = await client.put("/v1/config/max_prompt_kb", json={"value": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["key"] == "max_prompt_kb"
    assert body["data"]["value"] == 10
    assert "meta" in body


@pytest.mark.asyncio
async def test_set_config_upsert(client):
    await client.put("/v1/config/feature_x", json={"value": False})
    resp = await client.put("/v1/config/feature_x", json={"value": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["value"] is True


@pytest.mark.asyncio
async def test_get_config_list(client):
    await client.put("/v1/config/key_a", json={"value": "alpha"})
    await client.put("/v1/config/key_b", json={"value": 42})
    resp = await client.get("/v1/config")
    assert resp.status_code == 200
    keys = [item["key"] for item in resp.json()["data"]]
    assert "key_a" in keys
    assert "key_b" in keys


@pytest.mark.asyncio
async def test_set_config_object_value(client):
    resp = await client.put("/v1/config/limits", json={"value": {"rpm": 100, "tpm": 50000}})
    assert resp.status_code == 200
    assert resp.json()["data"]["value"]["rpm"] == 100


@pytest.mark.asyncio
async def test_set_config_list_value(client):
    resp = await client.put("/v1/config/allowed_models", json={"value": ["gpt-4o", "claude-3"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["value"] == ["gpt-4o", "claude-3"]


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["service"] == "dal"
