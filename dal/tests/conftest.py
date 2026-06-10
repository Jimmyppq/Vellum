import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.schema import metadata

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://vellum_user:changeme@localhost:5433/vellum_test",
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables once before the session using asyncio.run() — completely
    independent of pytest-asyncio's loop management, so no loop is shared with tests."""

    async def _create():
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        await engine.dispose()

    async def _drop():
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


@pytest_asyncio.fixture
async def db_session():
    """Each test gets a fresh NullPool engine and connection in its own event loop.
    Changes are rolled back after the test via the outer BEGIN.
    join_transaction_mode='create_savepoint' ensures repo-level commit() calls only
    release a SAVEPOINT, never the outer transaction."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield session
        await session.close()
        await conn.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """HTTP test client with the DAL app; get_session overridden with the test session.
    Sends X-Internal-Service-Token on every request so the auth middleware passes."""
    import os

    from app.database import get_session
    from main import app

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    token = os.getenv("INTERNAL_SERVICE_TOKEN", "test-token")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Internal-Service-Token": token},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
