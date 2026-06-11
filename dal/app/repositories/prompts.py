import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import executions, prompts
from app.repositories.errors import (
    InvalidStateTransition,
    PromptHasExecutions,
    PromptNotFound,
)
from app.schemas.requests import PromptCreate
from app.schemas.responses import PromptResponse

# State machine: target status -> allowed source statuses. Any transition not
# listed here (including same -> same) is rejected. "draft" is never a valid
# target: prompts only enter it on create; iterating means a new version.
ALLOWED_SOURCES = {
    "approved": {"draft", "deprecated"},
    "deprecated": {"approved"},
}


def _row_to_response(row) -> PromptResponse:
    return PromptResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        owner_id=row.owner_id,
        status=row.status,
        visibility=row.visibility,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
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
            is_deleted=False,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        ).returning(*prompts.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def get_by_id(self, id: UUID, include_deleted: bool = False) -> PromptResponse | None:
        stmt = select(prompts).where(prompts.c.id == id)
        if not include_deleted:
            stmt = stmt.where(prompts.c.is_deleted == False)  # noqa: E712
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def list(
        self,
        status: str | None = None,
        owner_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[PromptResponse]:
        stmt = select(prompts)
        if not include_deleted:
            stmt = stmt.where(prompts.c.is_deleted == False)  # noqa: E712
        if status:
            stmt = stmt.where(prompts.c.status == status)
        if owner_id:
            stmt = stmt.where(prompts.c.owner_id == owner_id)
        stmt = stmt.limit(limit).offset(offset).order_by(prompts.c.created_at.desc())
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]

    async def update_status(self, id: UUID, status: str) -> PromptResponse:
        now = datetime.now(timezone.utc)
        # Atomic compare-and-set: the WHERE clause enforces the state machine
        # and excludes soft-deleted prompts.
        allowed_sources = ALLOWED_SOURCES.get(status, set())
        stmt = (
            update(prompts)
            .where(
                prompts.c.id == id,
                prompts.c.is_deleted == False,  # noqa: E712
                prompts.c.status.in_(allowed_sources),
            )
            .values(status=status, updated_at=now)
            .returning(*prompts.c)
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if not row:
            await self._session.rollback()
            current = await self._session.execute(
                select(prompts.c.status, prompts.c.is_deleted).where(prompts.c.id == id)
            )
            current_row = current.fetchone()
            if not current_row or current_row.is_deleted:
                raise PromptNotFound(id)
            raise InvalidStateTransition(current_row.status, status)
        await self._session.commit()
        return _row_to_response(row)

    async def soft_delete(self, id: UUID) -> PromptResponse:
        now = datetime.now(timezone.utc)
        # Single atomic statement: the business rule (no executions) lives in
        # the WHERE clause, so there is no window between check and delete.
        stmt = (
            update(prompts)
            .where(
                prompts.c.id == id,
                prompts.c.is_deleted == False,  # noqa: E712
                ~exists(select(executions.c.id).where(executions.c.prompt_id == id)),
            )
            .values(is_deleted=True, deleted_at=now, updated_at=now)
            .returning(*prompts.c)
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if not row:
            await self._session.rollback()
            current = await self._session.execute(
                select(prompts.c.is_deleted).where(prompts.c.id == id)
            )
            current_row = current.fetchone()
            if not current_row or current_row.is_deleted:
                raise PromptNotFound(id)
            raise PromptHasExecutions(id)
        await self._session.commit()
        return _row_to_response(row)
