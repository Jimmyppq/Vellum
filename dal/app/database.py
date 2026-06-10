from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.providers.router import get_provider

_settings = get_settings()
_provider = get_provider(_settings)
_engine = _provider.get_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they do not exist. Called once on startup."""
    from app.models.schema import metadata
    async with _engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
