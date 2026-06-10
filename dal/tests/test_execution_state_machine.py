import uuid
from decimal import Decimal

import pytest

from app.repositories.errors import (
    ExecutionNotFound,
    InvalidPayloadForTransition,
    InvalidStateTransition,
)
from app.repositories.executions import ExecutionsRepository
from app.schemas.requests import ExecutionCreate, PromptCreate, UserCreate, VersionCreate


async def _setup(session):
    from app.repositories.prompt_versions import PromptVersionsRepository
    from app.repositories.prompts import PromptsRepository
    from app.repositories.users import UsersRepository

    user_repo = UsersRepository(session)
    user = await user_repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))
    prompt_repo = PromptsRepository(session)
    prompt = await prompt_repo.create(PromptCreate(name="SM Prompt", owner_id=user.id))
    version_repo = PromptVersionsRepository(session)
    version = await version_repo.create(VersionCreate(prompt_id=prompt.id, content="content", created_by=user.id))
    return user, prompt, version


async def _new_execution(session):
    user, prompt, version = await _setup(session)
    repo = ExecutionsRepository(session)
    execution = await repo.create(ExecutionCreate(
        prompt_id=prompt.id, version_id=version.id,
        executed_by=user.id, input_data={},
    ))
    return repo, execution


# ---------------------------------------------------------------------------
# 4.1 Transition matrix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_transitions_queued_running_completed(db_session):
    repo, execution = await _new_execution(db_session)
    updated = await repo.update_status(execution.id, "running")
    assert updated.status == "running"
    updated = await repo.update_status(execution.id, "completed")
    assert updated.status == "completed"


@pytest.mark.asyncio
async def test_valid_transition_running_failed(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    updated = await repo.update_status(execution.id, "failed")
    assert updated.status == "failed"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_valid_transition_queued_cancelled(db_session):
    repo, execution = await _new_execution(db_session)
    updated = await repo.update_status(execution.id, "cancelled")
    assert updated.status == "cancelled"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_terminal_state_is_immutable(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    await repo.update_status(execution.id, "failed", {"error": "boom"})
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(execution.id, "running")
    row = await repo.get_by_id(execution.id)
    assert row.status == "failed"
    assert row.output_data == {"error": "boom"}
    assert row.completed_at is not None


@pytest.mark.asyncio
async def test_same_to_same_transition_is_rejected(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    with pytest.raises(InvalidStateTransition) as exc_info:
        await repo.update_status(execution.id, "running")
    assert exc_info.value.current == "running"
    assert exc_info.value.requested == "running"


@pytest.mark.asyncio
async def test_transition_back_to_queued_is_rejected(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(execution.id, "queued")


@pytest.mark.asyncio
async def test_cancel_running_execution_is_rejected(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(execution.id, "cancelled")
    row = await repo.get_by_id(execution.id)
    assert row.status == "running"


# ---------------------------------------------------------------------------
# 4.2 404 vs 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_id_raises_not_found(db_session):
    repo = ExecutionsRepository(db_session)
    with pytest.raises(ExecutionNotFound):
        await repo.update_status(uuid.uuid4(), "running")


@pytest.mark.asyncio
async def test_endpoint_404_vs_409(client):
    resp = await client.patch(f"/v1/executions/{uuid.uuid4()}/status", json={"status": "running"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    exec_id = await _create_execution_via_api(client)
    await client.patch(f"/v1/executions/{exec_id}/status", json={"status": "running"})
    resp = await client.patch(f"/v1/executions/{exec_id}/status", json={"status": "running"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


# ---------------------------------------------------------------------------
# 4.3 Payload rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_output_and_cost_persist_on_terminal_transition(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    updated = await repo.update_status(
        execution.id, "completed", {"result": "ok"}, Decimal("0.0042")
    )
    assert updated.output_data == {"result": "ok"}
    assert updated.cost == Decimal("0.0042")
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_output_on_non_terminal_transition_is_rejected(db_session):
    repo, execution = await _new_execution(db_session)
    with pytest.raises(InvalidPayloadForTransition):
        await repo.update_status(execution.id, "running", {"result": "early"})
    row = await repo.get_by_id(execution.id)
    assert row.status == "queued"
    assert row.output_data is None


@pytest.mark.asyncio
async def test_cost_on_non_terminal_transition_is_rejected(db_session):
    repo, execution = await _new_execution(db_session)
    with pytest.raises(InvalidPayloadForTransition):
        await repo.update_status(execution.id, "running", None, Decimal("0.01"))


@pytest.mark.asyncio
async def test_terminal_transition_without_payload(db_session):
    repo, execution = await _new_execution(db_session)
    await repo.update_status(execution.id, "running")
    updated = await repo.update_status(execution.id, "failed")
    assert updated.completed_at is not None
    assert updated.output_data is None
    assert updated.cost is None


@pytest.mark.asyncio
async def test_endpoint_payload_on_non_terminal_returns_400(client):
    exec_id = await _create_execution_via_api(client)
    resp = await client.patch(
        f"/v1/executions/{exec_id}/status",
        json={"status": "running", "output_data": {"x": 1}},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PAYLOAD_FOR_TRANSITION"
    get_resp = await client.get(f"/v1/executions/{exec_id}")
    assert get_resp.json()["data"]["status"] == "queued"


# ---------------------------------------------------------------------------
# 4.4 Compare-and-set: a transition consumed once cannot be consumed again.
# True multi-connection concurrency is not reproducible under the test
# fixtures (each test runs inside an outer rolled-back transaction), but the
# guarantee comes from the WHERE clause itself: the losing UPDATE matches
# zero rows regardless of interleaving.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cas_transition_can_only_be_consumed_once(db_session):
    repo, execution = await _new_execution(db_session)
    first = await repo.update_status(execution.id, "running")
    assert first.status == "running"
    with pytest.raises(InvalidStateTransition):
        await repo.update_status(execution.id, "running")


# ---------------------------------------------------------------------------
# 4.5 Error format
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_409_error_format(client):
    exec_id = await _create_execution_via_api(client)
    await client.patch(f"/v1/executions/{exec_id}/status", json={"status": "cancelled"})
    resp = await client.patch(f"/v1/executions/{exec_id}/status", json={"status": "running"})
    assert resp.status_code == 409
    body = resp.json()["error"]
    assert body["code"] == "INVALID_STATE_TRANSITION"
    assert "cancelled" in body["message"]
    assert "running" in body["message"]
    assert body["trace_id"]
    assert body["trace_id"] == resp.headers["X-Trace-Id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_execution_via_api(client) -> str:
    user_resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex}@test.com"})
    owner_id = user_resp.json()["data"]["id"]
    prompt_resp = await client.post("/v1/prompts", json={"name": "SM EP", "owner_id": owner_id})
    prompt_id = prompt_resp.json()["data"]["id"]
    ver_resp = await client.post(f"/v1/prompts/{prompt_id}/versions", json={
        "content": "body", "created_by": owner_id
    })
    ver_id = ver_resp.json()["data"]["id"]
    exec_resp = await client.post("/v1/executions", json={
        "prompt_id": prompt_id, "version_id": ver_id,
        "executed_by": owner_id, "input_data": {}
    })
    return exec_resp.json()["data"]["id"]
