import uuid
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import prompts
from app.schemas.requests import PromptCreate
from app.schemas.responses import PromptResponse

VALID_STATUSES = {"draft", "approved", "deprecated"}


def _row_to_response(row) -> PromptResponse:
    return PromptResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        owner_id=row.owner_id,
        status=row.status,
        visibility=row.visibility,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PromptsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: PromptCreate) -> PromptResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()
        stmt = prompts.insert().values(
            id=row_id,
            name=data.name,
            description=data.description,
            owner_id=data.owner_id,
            status="draft",
            visibility=data.visibility,
            created_at=now,
            updated_at=now,
        ).returning(*prompts.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def get_by_id(self, id: UUID) -> PromptResponse | None:
        stmt = select(prompts).where(prompts.c.id == id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def list(
        self,
        status: str | None = None,
        owner_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptResponse]:
        stmt = select(prompts)
        if status:
            stmt = stmt.where(prompts.c.status == status)
        if owner_id:
            stmt = stmt.where(prompts.c.owner_id == owner_id)
        stmt = stmt.limit(limit).offset(offset).order_by(prompts.c.created_at.desc())
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]

    async def update_status(self, id: UUID, status: str) -> PromptResponse:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")
        now = datetime.now(timezone.utc)
        stmt = (
            update(prompts)
            .where(prompts.c.id == id)
            .values(status=status, updated_at=now)
            .returning(*prompts.c)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.fetchone()
        if not row:
            raise ValueError(f"Prompt {id} not found")
        return _row_to_response(row)

    async def delete(self, id: UUID) -> bool:
        stmt = delete(prompts).where(prompts.c.id == id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0
