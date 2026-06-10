import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class PostgresProvider(BaseProvider):

    def __init__(self, settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None

    def get_engine(self) -> AsyncEngine:
        if self._engine is None:
            s = self._settings
            self._engine = create_async_engine(
                s.async_database_url,
                pool_size=s.DB_POOL_SIZE,
                max_overflow=s.DB_MAX_OVERFLOW,
                pool_timeout=s.DB_POOL_TIMEOUT,
                echo=False,
            )
            logger.info(
                "PostgreSQL engine created",
                extra={"action": "provider.init", "status": "success",
                       "message": f"Connected to {s.safe_database_url}"},
            )
        return self._engine

    async def health_check(self) -> bool:
        try:
            async with self.get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning(
                "Database health check failed",
                extra={"action": "provider.health_check", "status": "failure",
                       "message": str(exc)},
            )
            return False
