import uuid

import pytest

from app.repositories.errors import InvalidStateTransition
from app.repositories.executions import ExecutionsRepository
from app.repositories.prompt_versions import PromptVersionsRepository
from app.repositories.prompts import PromptsRepository
from app.repositories.users import UsersRepository
from app.schemas.requests import ExecutionCreate, PromptCreate, UserCreate, VersionCreate


async def _setup(session):
    user_repo = UsersRepository(session)
    user = await user_repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))
    prompt_repo = PromptsRepository(session)
    prompt = await prompt_repo.create(PromptCreate(name="Exec Prompt", owner_id=user.id))
    version_repo = PromptVersionsRepository(session)
    version = await version_repo.create(VersionCreate(prompt_id=prompt.id, content="content", created_by=user.id))
    return user, prompt, version


@pytest.mark.asyncio
async def test_create_execution(db_session):
    user, prompt, version = await _setup(db_session)
    repo = ExecutionsRepository(db_session)
    execution = await repo.create(ExecutionCreate(
        prompt_id=prompt.id,
        version_id=version.id,
        executed_by=user.id,
        input_data={"key": "value"},
    ))
    assert execution.id is not None
    assert execution.status == "queued"
    assert execution.completed_at is None


@pytest.mark.asyncio
async def test_update_status_completed_sets_completed_at(db_session):
    user, prompt, version = await _setup(db_session)
    repo = ExecutionsRepository(db_session)
    execution = await repo.create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id,
        executed_by=user.id, input_data={},
    ))
    await repo.update_status(execution.id, "running")
    updated = await repo.update_status(execution.id, "completed", {"result": "ok"})
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.output_data == {"result": "ok"}


@pytest.mark.asyncio
async def test_update_status_failed_sets_completed_at(db_session):
    user, prompt, version = await _setup(db_session)
    repo = ExecutionsRepository(db_session)
    execution = await repo.create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id,
        executed_by=user.id, input_data={},
    ))
    await repo.update_status(execution.id, "running")
    updated = await repo.update_status(execution.id, "failed")
    assert updated.status == "failed"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_update_status_running_does_not_set_completed_at(db_session):
    user, prompt, version = await _setup(db_session)
    repo = ExecutionsRepository(db_session)
    execution = await repo.create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id,
        executed_by=user.id, input_data={},
    ))
    updated = await repo.update_status(execution.id, "running")
    assert updated.completed_at is None


@pytest.mark.asyncio
async def test_update_status_invalid_raises(db_session):
    user, prompt, version = await _setup(db_session)
    repo = ExecutionsRepository(db_session)
    execution = await repo.create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id,
        executed_by=user.id, input_data={},
    ))
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(execution.id, "bogus")


@pytest.mark.asyncio
async def test_list_by_prompt(db_session):
    user, prompt, version = await _setup(db_session)
    repo = ExecutionsRepository(db_session)
    for _ in range(3):
        await repo.create(ExecutionCreate(
            prompt_id=prompt.id, version_id=version.id,
            executed_by=user.id, input_data={},
        ))
    items = await repo.list_by_prompt(prompt.id)
    assert len(items) >= 3


@pytest.mark.asyncio
async def test_execution_endpoint_patch_status(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "EP", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]
    ver_resp = await client.post(f"/v1/prompts/{prompt_id}/versions", json={
        "content": "body", "created_by": owner_id
    })
    ver_id = ver_resp.json()["data"]["id"]
    exec_resp = await client.post("/v1/executions", json={
        "prompt_id": prompt_id, "version_id": ver_id,
        "executed_by": owner_id, "input_data": {}
    })
    assert exec_resp.status_code == 201
    exec_id = exec_resp.json()["data"]["id"]

    run_resp = await client.patch(f"/v1/executions/{exec_id}/status", json={"status": "running"})
    assert run_resp.status_code == 200

    patch_resp = await client.patch(f"/v1/executions/{exec_id}/status", json={"status": "completed"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["completed_at"] is not None
