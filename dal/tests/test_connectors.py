import uuid

import pytest

from app.repositories.connectors import ConnectorsRepository
from app.schemas.requests import ConnectorCreate


@pytest.mark.asyncio
async def test_create_connector(db_session):
    repo = ConnectorsRepository(db_session)
    connector = await repo.create(ConnectorCreate(type="slack", name="Slack Prod"))
    assert connector.id is not None
    assert connector.type == "slack"
    assert connector.is_active is True


@pytest.mark.asyncio
async def test_get_connector_by_id(db_session):
    repo = ConnectorsRepository(db_session)
    created = await repo.create(ConnectorCreate(type="confluence", name="Confluence"))
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_get_nonexistent_connector_returns_none(db_session):
    repo = ConnectorsRepository(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_list_active_excludes_inactive(db_session):
    repo = ConnectorsRepository(db_session)
    active = await repo.create(ConnectorCreate(type="zapier", name="Active", is_active=True))
    inactive = await repo.create(ConnectorCreate(type="zapier", name="Inactive", is_active=False))
    items = await repo.list_active()
    ids = [c.id for c in items]
    assert active.id in ids
    assert inactive.id not in ids


@pytest.mark.asyncio
async def test_set_active_false(db_session):
    repo = ConnectorsRepository(db_session)
    connector = await repo.create(ConnectorCreate(type="slack", name="Disable Me"))
    updated = await repo.set_active(connector.id, False)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_set_active_nonexistent_raises(db_session):
    repo = ConnectorsRepository(db_session)
    with pytest.raises(ValueError, match="not found"):
        await repo.set_active(uuid.uuid4(), False)


@pytest.mark.asyncio
async def test_create_connector_endpoint(client):
    resp = await client.post("/v1/connectors", json={"type": "slack", "name": "Slack API"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["type"] == "slack"
    assert body["data"]["is_active"] is True
    assert "meta" in body


@pytest.mark.asyncio
async def test_list_connectors_endpoint(client):
    await client.post("/v1/connectors", json={"type": "confluence", "name": "C1"})
    await client.post("/v1/connectors", json={"type": "confluence", "name": "C2"})
    resp = await client.get("/v1/connectors")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 2


@pytest.mark.asyncio
async def test_get_connector_404(client):
    resp = await client.get(f"/v1/connectors/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_connector_active_endpoint(client):
    create_resp = await client.post("/v1/connectors", json={"type": "zapier", "name": "Z"})
    connector_id = create_resp.json()["data"]["id"]

    resp = await client.patch(f"/v1/connectors/{connector_id}/active", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_patch_connector_active_404(client):
    resp = await client.patch(f"/v1/connectors/{uuid.uuid4()}/active", json={"is_active": True})
    assert resp.status_code == 404
