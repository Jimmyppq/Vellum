import uuid

import pytest

from app.repositories.transcript_versions import TranscriptVersionsRepository
from app.repositories.transcripts import TranscriptsRepository
from app.repositories.users import UsersRepository
from app.schemas.requests import TranscriptCreate, TranscriptVersionCreate, UserCreate


async def _create_user(session):
    repo = UsersRepository(session)
    return await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))


async def _create_transcript(session, owner_id):
    repo = TranscriptsRepository(session)
    return await repo.create(TranscriptCreate(name="Test Transcript", owner_id=owner_id))


@pytest.mark.asyncio
async def test_create_transcript(db_session):
    user = await _create_user(db_session)
    repo = TranscriptsRepository(db_session)
    t = await repo.create(TranscriptCreate(name="Meeting recording", owner_id=user.id))
    assert t.id is not None
    assert t.name == "Meeting recording"
    assert t.status == "pending"


@pytest.mark.asyncio
async def test_get_transcript_by_id(db_session):
    user = await _create_user(db_session)
    t = await _create_transcript(db_session, user.id)
    repo = TranscriptsRepository(db_session)
    found = await repo.get_by_id(t.id)
    assert found is not None
    assert found.id == t.id


@pytest.mark.asyncio
async def test_get_nonexistent_transcript_returns_none(db_session):
    repo = TranscriptsRepository(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_list_transcripts_by_status(db_session):
    user = await _create_user(db_session)
    repo = TranscriptsRepository(db_session)
    t = await repo.create(TranscriptCreate(name="T1", owner_id=user.id))
    await repo.update_status(t.id, "completed")
    await repo.create(TranscriptCreate(name="T2", owner_id=user.id))
    completed = await repo.list(status="completed", owner_id=user.id)
    assert all(item.status == "completed" for item in completed)


@pytest.mark.asyncio
async def test_update_transcript_status_empty_raises(db_session):
    user = await _create_user(db_session)
    t = await _create_transcript(db_session, user.id)
    repo = TranscriptsRepository(db_session)
    with pytest.raises(ValueError):
        await repo.update_status(t.id, "")


@pytest.mark.asyncio
async def test_delete_transcript(db_session):
    user = await _create_user(db_session)
    t = await _create_transcript(db_session, user.id)
    repo = TranscriptsRepository(db_session)
    assert await repo.delete(t.id) is True
    assert await repo.get_by_id(t.id) is None


@pytest.mark.asyncio
async def test_transcript_version_activation_is_atomic(db_session):
    user = await _create_user(db_session)
    t = await _create_transcript(db_session, user.id)
    ver_repo = TranscriptVersionsRepository(db_session)

    v1 = await ver_repo.create(TranscriptVersionCreate(
        transcript_id=t.id, content="v1", created_by=user.id, is_active=True
    ))
    assert v1.is_active is True
    assert v1.version_number == 1

    v2 = await ver_repo.create(TranscriptVersionCreate(
        transcript_id=t.id, content="v2", created_by=user.id, is_active=True
    ))
    assert v2.is_active is True
    assert v2.version_number == 2

    v1_refreshed = await ver_repo.get_by_id(v1.id)
    assert v1_refreshed.is_active is False

    active = await ver_repo.get_active(t.id)
    assert active.id == v2.id


@pytest.mark.asyncio
async def test_get_active_version_returns_none_when_none(db_session):
    user = await _create_user(db_session)
    t = await _create_transcript(db_session, user.id)
    ver_repo = TranscriptVersionsRepository(db_session)
    assert await ver_repo.get_active(t.id) is None


@pytest.mark.asyncio
async def test_list_versions_by_transcript(db_session):
    user = await _create_user(db_session)
    t = await _create_transcript(db_session, user.id)
    ver_repo = TranscriptVersionsRepository(db_session)
    for content in ["a", "b", "c"]:
        await ver_repo.create(TranscriptVersionCreate(
            transcript_id=t.id, content=content, created_by=user.id
        ))
    versions = await ver_repo.list_by_transcript(t.id)
    assert len(versions) == 3
    assert [v.version_number for v in versions] == [1, 2, 3]


@pytest.mark.asyncio
async def test_create_transcript_endpoint(client):
    user_resp = await client.post("/v1/users", json={
        "username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"
    })
    owner_id = user_resp.json()["data"]["id"]
    resp = await client.post("/v1/transcripts", json={"name": "API Transcript", "owner_id": owner_id})
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["name"] == "API Transcript"
    assert "meta" in body


@pytest.mark.asyncio
async def test_get_transcript_404(client):
    resp = await client.get(f"/v1/transcripts/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_and_get_active_version_endpoint(client):
    user_resp = await client.post("/v1/users", json={
        "username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"
    })
    owner_id = user_resp.json()["data"]["id"]
    t_resp = await client.post("/v1/transcripts", json={"name": "T", "owner_id": owner_id})
    t_id = t_resp.json()["data"]["id"]

    ver_resp = await client.post(f"/v1/transcripts/{t_id}/versions", json={
        "content": "transcript text", "created_by": owner_id, "is_active": True
    })
    assert ver_resp.status_code == 201
    assert ver_resp.json()["data"]["is_active"] is True

    active_resp = await client.get(f"/v1/transcripts/{t_id}/versions/active")
    assert active_resp.status_code == 200
    assert active_resp.json()["data"]["content"] == "transcript text"


@pytest.mark.asyncio
async def test_get_active_version_404_endpoint(client):
    user_resp = await client.post("/v1/users", json={
        "username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"
    })
    owner_id = user_resp.json()["data"]["id"]
    t_resp = await client.post("/v1/transcripts", json={"name": "NoVer", "owner_id": owner_id})
    t_id = t_resp.json()["data"]["id"]
    resp = await client.get(f"/v1/transcripts/{t_id}/versions/active")
    assert resp.status_code == 404
