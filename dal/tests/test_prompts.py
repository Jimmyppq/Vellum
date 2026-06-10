import uuid

import pytest

from app.repositories.prompt_versions import PromptVersionsRepository
from app.repositories.prompts import PromptsRepository
from app.repositories.users import UsersRepository
from app.schemas.requests import PromptCreate, UserCreate, VersionCreate


async def _create_user(session):
    repo = UsersRepository(session)
    return await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))


@pytest.mark.asyncio
async def test_create_prompt(db_session):
    user = await _create_user(db_session)
    repo = PromptsRepository(db_session)
    prompt = await repo.create(PromptCreate(name="Test Prompt", owner_id=user.id))
    assert prompt.id is not None
    assert prompt.name == "Test Prompt"
    assert prompt.status == "draft"


@pytest.mark.asyncio
async def test_get_prompt_by_id(db_session):
    user = await _create_user(db_session)
    repo = PromptsRepository(db_session)
    created = await repo.create(PromptCreate(name="Find Me", owner_id=user.id))
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_get_nonexistent_prompt_returns_none(db_session):
    repo = PromptsRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_list_prompts_by_status(db_session):
    user = await _create_user(db_session)
    repo = PromptsRepository(db_session)
    p1 = await repo.create(PromptCreate(name="Draft One", owner_id=user.id))
    await repo.update_status(p1.id, "approved")
    await repo.create(PromptCreate(name="Draft Two", owner_id=user.id))
    approved = await repo.list(status="approved", owner_id=user.id)
    assert all(p.status == "approved" for p in approved)


@pytest.mark.asyncio
async def test_update_prompt_status_invalid_raises(db_session):
    user = await _create_user(db_session)
    repo = PromptsRepository(db_session)
    prompt = await repo.create(PromptCreate(name="Status Test", owner_id=user.id))
    with pytest.raises(ValueError):
        await repo.update_status(prompt.id, "invalid_status")


@pytest.mark.asyncio
async def test_delete_prompt(db_session):
    user = await _create_user(db_session)
    repo = PromptsRepository(db_session)
    prompt = await repo.create(PromptCreate(name="To Delete", owner_id=user.id))
    deleted = await repo.delete(prompt.id)
    assert deleted is True
    assert await repo.get_by_id(prompt.id) is None


@pytest.mark.asyncio
async def test_version_activation_is_atomic(db_session):
    user = await _create_user(db_session)
    prompt_repo = PromptsRepository(db_session)
    prompt = await prompt_repo.create(PromptCreate(name="Versioned", owner_id=user.id))

    version_repo = PromptVersionsRepository(db_session)
    v1 = await version_repo.create(VersionCreate(
        prompt_id=prompt.id, content="v1 content", created_by=user.id, is_active=True
    ))
    assert v1.is_active is True
    assert v1.version_number == 1

    v2 = await version_repo.create(VersionCreate(
        prompt_id=prompt.id, content="v2 content", created_by=user.id, is_active=True
    ))
    assert v2.is_active is True
    assert v2.version_number == 2

    # v1 must now be inactive
    v1_refreshed = await version_repo.get_by_id(v1.id)
    assert v1_refreshed.is_active is False

    active = await version_repo.get_active(prompt.id)
    assert active.id == v2.id


@pytest.mark.asyncio
async def test_get_active_version_returns_none_when_none(db_session):
    user = await _create_user(db_session)
    prompt_repo = PromptsRepository(db_session)
    prompt = await prompt_repo.create(PromptCreate(name="No Active", owner_id=user.id))
    version_repo = PromptVersionsRepository(db_session)
    result = await version_repo.get_active(prompt.id)
    assert result is None


@pytest.mark.asyncio
async def test_create_prompt_endpoint(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    assert user_resp.status_code == 201
    owner_id = user_resp.json()["data"]["id"]

    resp = await client.post("/v1/prompts", json={"name": "API Prompt", "owner_id": owner_id})
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["name"] == "API Prompt"
    assert "meta" in body
    assert "request_id" in body["meta"]


@pytest.mark.asyncio
async def test_get_prompt_404(client):
    resp = await client.get(f"/v1/prompts/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_active_version_404(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "NoVer", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]
    resp = await client.get(f"/v1/prompts/{prompt_id}/versions/active")
    assert resp.status_code == 404
