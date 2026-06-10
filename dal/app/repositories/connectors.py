import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import connectors
from app.schemas.requests import ConnectorCreate
from app.schemas.responses import ConnectorResponse


def _row_to_response(row) -> ConnectorResponse:
    return ConnectorResponse(
        id=row.id,
        type=row.type,
        name=row.name,
        is_active=row.is_active,
        created_at=row.created_at,
    )


class ConnectorsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ConnectorCreate) -> ConnectorResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()
        stmt = connectors.insert().values(
            id=row_id,
            type=data.type,
            name=data.name,
            is_active=data.is_active,
            created_at=now,
        ).returning(*connectors.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def get_by_id(self, id: UUID) -> ConnectorResponse | None:
        stmt = select(connectors).where(connectors.c.id == id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def list_active(self) -> list[ConnectorResponse]:
        stmt = select(connectors).where(connectors.c.is_active == True)  # noqa: E712
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]

    async def set_active(self, id: UUID, is_active: bool) -> ConnectorResponse:
        stmt = (
            update(connectors)
            .where(connectors.c.id == id)
            .values(is_active=is_active)
            .returning(*connectors.c)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.fetchone()
        if not row:
            raise ValueError(f"Connector {id} not found")
        return _row_to_response(row)
