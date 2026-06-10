import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.providers.router import get_provider

logger = logging.getLogger("app.database")

_settings = get_settings()
_provider = get_provider(_settings)
_engine = _provider.get_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=False, autoflush=False
)

MIGRATE_HINT = "run `docker compose run --rm dal-migrate` to apply migrations"


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def _expected_head() -> str:
    """Head revision of migrations/versions/, resolved from the code."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    base_dir = Path(__file__).resolve().parent.parent  # dal/
    cfg = Config(str(base_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(base_dir / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if head is None:
        raise RuntimeError("No Alembic migrations found in migrations/versions/")
    return head


async def verify_schema_version(engine: AsyncEngine | None = None) -> None:
    """Fail-fast schema gate: abort startup unless the database schema is at
    the Alembic head. The service never runs DDL — schema changes are applied
    exclusively by the dal-migrate ephemeral container."""
    from alembic.runtime.migration import MigrationContext

    engine = engine or _engine
    head = _expected_head()

    def _current_revision(sync_conn) -> str | None:
        return MigrationContext.configure(sync_conn).get_current_revision()

    try:
        async with engine.connect() as conn:
            current = await conn.run_sync(_current_revision)
    except (OperationalError, InterfaceError, OSError) as exc:
        msg = (
            f"Database unreachable at {_settings.safe_database_url} — "
            "cannot verify schema version"
        )
        logger.error(msg, extra={"action": "verify_schema_version", "status": "failure"})
        raise RuntimeError(msg) from exc

    if current is None:
        msg = f"Database schema is not migrated (no alembic_version table) — {MIGRATE_HINT}"
        logger.error(msg, extra={"action": "verify_schema_version", "status": "failure"})
        raise RuntimeError(msg)

    if current != head:
        msg = (
            f"Database schema is at revision {current} but the code expects "
            f"head {head} — {MIGRATE_HINT}"
        )
        logger.error(msg, extra={"action": "verify_schema_version", "status": "failure"})
        raise RuntimeError(msg)

    logger.info(
        f"Database schema verified at head {head}",
        extra={"action": "verify_schema_version", "status": "success"},
    )
