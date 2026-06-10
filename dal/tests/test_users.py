import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.users import UsersRepository
from app.schemas.requests import UserCreate


@pytest.mark.asyncio
async def test_create_user(db_session):
    repo = UsersRepository(db_session)
    user = await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))
    assert user.id is not None
    assert user.is_active is True


@pytest.mark.asyncio
async def test_get_user_by_id(db_session):
    repo = UsersRepository(db_session)
    created = await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex}@test.com"))
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_get_nonexistent_user_returns_none(db_session):
    repo = UsersRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_by_email_case_insensitive(db_session):
    repo = UsersRepository(db_session)
    email_base = uuid.uuid4().hex
    await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=f"{email_base}@test.com"))
    found = await repo.get_by_email(f"{email_base.upper()}@TEST.COM")
    assert found is not None


@pytest.mark.asyncio
async def test_duplicate_email_raises_integrity_error(db_session):
    repo = UsersRepository(db_session)
    email = f"{uuid.uuid4().hex}@test.com"
    await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=email))
    with pytest.raises(IntegrityError):
        await repo.create(UserCreate(username=f"u{uuid.uuid4().hex[:8]}", email=email))


@pytest.mark.asyncio
async def test_assign_role_nonexistent_user_raises(db_session):
    repo = UsersRepository(db_session)
    with pytest.raises(ValueError, match="not found"):
        await repo.assign_role(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_create_user_endpoint(client):
    username = f"u{uuid.uuid4().hex[:8]}"
    email = f"{uuid.uuid4().hex}@test.com"
    resp = await client.post("/v1/users", json={"username": username, "email": email})
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["username"] == username
    assert "meta" in body


@pytest.mark.asyncio
async def test_create_user_duplicate_email_returns_409(client):
    email = f"{uuid.uuid4().hex}@test.com"
    await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": email})
    resp = await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": email})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "USER_EMAIL_CONFLICT"


@pytest.mark.asyncio
async def test_get_user_404(client):
    resp = await client.get(f"/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_by_email_endpoint(client):
    email = f"{uuid.uuid4().hex}@test.com"
    await client.post("/v1/users", json={"username": f"u{uuid.uuid4().hex[:8]}", "email": email})
    resp = await client.get(f"/v1/users/email/{email}")
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == email
