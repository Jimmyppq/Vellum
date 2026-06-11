"""Tests del ciclo de vida de prompts/transcripts: soft delete condicionado a
ausencia de ejecuciones, visibilidad de soft-deleted y máquina de estados de
prompts. Ver openspec/specs (dal-prompt-lifecycle)."""
import os
import subprocess
import uuid

import pytest

from app.repositories.errors import (
    InvalidStateTransition,
    PromptHasExecutions,
    PromptNotFound,
    TranscriptHasExecutions,
    TranscriptNotFound,
)
from app.repositories.executions import ExecutionsRepository
from app.repositories.prompt_versions import PromptVersionsRepository
from app.repositories.prompts import PromptsRepository
from app.repositories.transcripts import TranscriptsRepository
from app.repositories.users import UsersRepository
from app.schemas.requests import (
    ExecutionCreate,
    PromptCreate,
    TranscriptCreate,
    UserCreate,
    VersionCreate,
)


async def _user(session):
    repo = UsersRepository(session)
    return await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))


async def _prompt(session, owner_id):
    return await PromptsRepository(session).create(PromptCreate(name="SD Prompt", owner_id=owner_id))


async def _prompt_with_execution(session):
    user = await _user(session)
    prompt = await _prompt(session, user.id)
    version = await PromptVersionsRepository(session).create(
        VersionCreate(prompt_id=prompt.id, content="content", created_by=user.id)
    )
    execution = await ExecutionsRepository(session).create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id,
        executed_by=user.id, input_data={},
    ))
    return user, prompt, execution


# ---------------------------------------------------------------------------
# 6.1 Soft delete de prompts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_prompt_without_executions(db_session):
    user = await _user(db_session)
    prompt = await _prompt(db_session, user.id)
    repo = PromptsRepository(db_session)
    deleted = await repo.soft_delete(prompt.id)
    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None
    # the row still exists
    assert (await repo.get_by_id(prompt.id, include_deleted=True)) is not None


@pytest.mark.asyncio
async def test_soft_delete_prompt_with_executions_is_rejected(db_session):
    _, prompt, _ = await _prompt_with_execution(db_session)
    repo = PromptsRepository(db_session)
    with pytest.raises(PromptHasExecutions) as exc_info:
        await repo.soft_delete(prompt.id)
    assert "deprecate" in str(exc_info.value)
    row = await repo.get_by_id(prompt.id)
    assert row is not None and row.is_deleted is False


@pytest.mark.asyncio
async def test_soft_delete_prompt_twice_raises_not_found(db_session):
    user = await _user(db_session)
    prompt = await _prompt(db_session, user.id)
    repo = PromptsRepository(db_session)
    await repo.soft_delete(prompt.id)
    with pytest.raises(PromptNotFound):
        await repo.soft_delete(prompt.id)


@pytest.mark.asyncio
async def test_soft_delete_unknown_prompt_raises_not_found(db_session):
    with pytest.raises(PromptNotFound):
        await PromptsRepository(db_session).soft_delete(uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_endpoint_contract(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "DEL", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]

    resp = await client.delete(f"/v1/prompts/{prompt_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is True

    resp = await client.delete(f"/v1/prompts/{prompt_id}")
    assert resp.status_code == 404

    resp = await client.delete(f"/v1/prompts/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_endpoint_409_with_executions(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "DEL409", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]
    ver_resp = await client.post(f"/v1/prompts/{prompt_id}/versions", json={"content": "c", "created_by": owner_id})
    ver_id = ver_resp.json()["data"]["id"]
    await client.post("/v1/executions", json={
        "prompt_id": prompt_id, "version_id": ver_id,
        "executed_by": owner_id, "input_data": {},
    })

    resp = await client.delete(f"/v1/prompts/{prompt_id}")
    assert resp.status_code == 409
    body = resp.json()["error"]
    assert body["code"] == "PROMPT_HAS_EXECUTIONS"
    assert body["trace_id"]


# ---------------------------------------------------------------------------
# 6.2 Visibilidad
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_deleted_hidden_from_reads(db_session):
    user = await _user(db_session)
    prompt = await _prompt(db_session, user.id)
    repo = PromptsRepository(db_session)
    await repo.soft_delete(prompt.id)

    assert await repo.get_by_id(prompt.id) is None
    listed = await repo.list(owner_id=user.id)
    assert all(p.id != prompt.id for p in listed)

    visible = await repo.get_by_id(prompt.id, include_deleted=True)
    assert visible is not None and visible.is_deleted is True
    listed = await repo.list(owner_id=user.id, include_deleted=True)
    assert any(p.id == prompt.id for p in listed)


@pytest.mark.asyncio
async def test_endpoint_visibility_and_include_deleted(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "VIS", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]
    await client.delete(f"/v1/prompts/{prompt_id}")

    assert (await client.get(f"/v1/prompts/{prompt_id}")).status_code == 404
    resp = await client.get(f"/v1/prompts/{prompt_id}?include_deleted=true")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is True

    # subresources of a deleted parent are 404, status is immutable
    assert (await client.get(f"/v1/prompts/{prompt_id}/versions")).status_code == 404
    assert (await client.post(
        f"/v1/prompts/{prompt_id}/versions", json={"content": "c", "created_by": owner_id}
    )).status_code == 404
    assert (await client.patch(
        f"/v1/prompts/{prompt_id}/status", json={"status": "approved"}
    )).status_code == 404


# ---------------------------------------------------------------------------
# 6.3 Máquina de estados de prompts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prompt_status_valid_cycle(db_session):
    user = await _user(db_session)
    prompt = await _prompt(db_session, user.id)
    repo = PromptsRepository(db_session)
    assert (await repo.update_status(prompt.id, "approved")).status == "approved"
    assert (await repo.update_status(prompt.id, "deprecated")).status == "deprecated"
    assert (await repo.update_status(prompt.id, "approved")).status == "approved"


@pytest.mark.asyncio
async def test_prompt_status_invalid_transitions(db_session):
    user = await _user(db_session)
    prompt = await _prompt(db_session, user.id)
    repo = PromptsRepository(db_session)

    # draft -> deprecated: invalid
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(prompt.id, "deprecated")
    # same -> same: invalid
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(prompt.id, "draft")

    await repo.update_status(prompt.id, "approved")
    # any -> draft: invalid
    with pytest.raises(InvalidStateTransition) as exc_info:
        await repo.update_status(prompt.id, "draft")
    assert exc_info.value.current == "approved"
    assert exc_info.value.requested == "draft"
    # same -> same: invalid
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(prompt.id, "approved")

    row = await repo.get_by_id(prompt.id)
    assert row.status == "approved"


@pytest.mark.asyncio
async def test_prompt_status_endpoint_409(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "SM", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]

    resp = await client.patch(f"/v1/prompts/{prompt_id}/status", json={"status": "deprecated"})
    assert resp.status_code == 409
    body = resp.json()["error"]
    assert body["code"] == "INVALID_STATE_TRANSITION"
    assert "draft" in body["message"]
    assert "deprecated" in body["message"]
    assert body["trace_id"] == resp.headers["X-Trace-Id"]


# ---------------------------------------------------------------------------
# 6.4 Soft delete de transcripts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_transcript(db_session):
    user = await _user(db_session)
    repo = TranscriptsRepository(db_session)
    t = await repo.create(TranscriptCreate(name="T", owner_id=user.id))
    deleted = await repo.soft_delete(t.id)
    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None
    assert await repo.get_by_id(t.id) is None
    assert (await repo.get_by_id(t.id, include_deleted=True)) is not None
    with pytest.raises(TranscriptNotFound):
        await repo.soft_delete(t.id)


@pytest.mark.asyncio
async def test_soft_delete_transcript_with_executions_is_rejected(db_session):
    user, prompt, _ = await _prompt_with_execution(db_session)
    t_repo = TranscriptsRepository(db_session)
    t = await t_repo.create(TranscriptCreate(name="T-exec", owner_id=user.id))
    version = await PromptVersionsRepository(db_session).create(
        VersionCreate(prompt_id=prompt.id, content="c2", created_by=user.id)
    )
    await ExecutionsRepository(db_session).create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id, transcript_id=t.id,
        executed_by=user.id, input_data={},
    ))
    with pytest.raises(TranscriptHasExecutions):
        await t_repo.soft_delete(t.id)
    assert (await t_repo.get_by_id(t.id)) is not None


@pytest.mark.asyncio
async def test_transcript_delete_endpoint(client):
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    t_resp = await client.post("/v1/transcripts", json={"name": "TDel", "owner_id": owner_id})
    t_id = t_resp.json()["data"]["id"]

    resp = await client.delete(f"/v1/transcripts/{t_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_deleted"] is True
    assert (await client.get(f"/v1/transcripts/{t_id}")).status_code == 404
    assert (await client.get(f"/v1/transcripts/{t_id}?include_deleted=true")).status_code == 200


# ---------------------------------------------------------------------------
# 6.5 Atomicidad CAS — el soft delete solo se consume una vez; la regla de
# negocio vive en el WHERE del UPDATE (NOT EXISTS), sin ventana check-then-act
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_consumed_only_once(db_session):
    user = await _user(db_session)
    prompt = await _prompt(db_session, user.id)
    repo = PromptsRepository(db_session)
    first = await repo.soft_delete(prompt.id)
    assert first.is_deleted is True
    with pytest.raises(PromptNotFound):
        await repo.soft_delete(prompt.id)


# ---------------------------------------------------------------------------
# 6.6 Migración reversible
# ---------------------------------------------------------------------------

async def test_soft_delete_migration_upgrade_and_downgrade():
    from tests.test_portable_types import CHECK_DB, DAL_DIR, _recreate_check_db

    await _recreate_check_db()
    env = {**os.environ, "DB_NAME": CHECK_DB}

    up = subprocess.run(["alembic", "upgrade", "head"], cwd=DAL_DIR, env=env, capture_output=True, text=True)
    assert up.returncode == 0, f"upgrade falló:\n{up.stdout}\n{up.stderr}"

    down = subprocess.run(["alembic", "downgrade", "-1"], cwd=DAL_DIR, env=env, capture_output=True, text=True)
    assert down.returncode == 0, f"downgrade falló:\n{down.stdout}\n{down.stderr}"

    up_again = subprocess.run(["alembic", "upgrade", "head"], cwd=DAL_DIR, env=env, capture_output=True, text=True)
    assert up_again.returncode == 0, f"re-upgrade falló:\n{up_again.stdout}\n{up_again.stderr}"
