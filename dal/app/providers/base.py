from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncEngine


class BaseProvider(ABC):

    @abstractmethod
    def get_engine(self) -> AsyncEngine:
        """Return the configured async SQLAlchemy engine for this database motor."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify connectivity with the database. Returns True on success, False on any error."""
        ...
