import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import executions, transcripts
from app.repositories.errors import TranscriptHasExecutions, TranscriptNotFound
from app.schemas.requests import TranscriptCreate
from app.schemas.responses import TranscriptResponse


def _row_to_response(row) -> TranscriptResponse:
    return TranscriptResponse(
        id=row.id,
        name=row.name,
        media_url=row.media_url,
        owner_id=row.owner_id,
        status=row.status,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class TranscriptsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TranscriptCreate) -> TranscriptResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()
        stmt = transcripts.insert().values(
            id=row_id,
            name=data.name,
            media_url=data.media_url,
            owner_id=data.owner_id,
            status=data.status,
            is_deleted=False,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        ).returning(*transcripts.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def get_by_id(self, id: UUID, include_deleted: bool = False) -> TranscriptResponse | None:
        stmt = select(transcripts).where(transcripts.c.id == id)
        if not include_deleted:
            stmt = stmt.where(transcripts.c.is_deleted == False)  # noqa: E712
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
    ) -> list[TranscriptResponse]:
        stmt = select(transcripts)
        if not include_deleted:
            stmt = stmt.where(transcripts.c.is_deleted == False)  # noqa: E712
        if status:
            stmt = stmt.where(transcripts.c.status == status)
        if owner_id:
            stmt = stmt.where(transcripts.c.owner_id == owner_id)
        stmt = stmt.limit(limit).offset(offset).order_by(transcripts.c.created_at.desc())
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]

    async def update_status(self, id: UUID, status: str) -> TranscriptResponse:
        if not status or not status.strip():
            raise ValueError("status must not be empty")
        now = datetime.now(timezone.utc)
        stmt = (
            update(transcripts)
            .where(
                transcripts.c.id == id,
                transcripts.c.is_deleted == False,  # noqa: E712
            )
            .values(status=status, updated_at=now)
            .returning(*transcripts.c)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.fetchone()
        if not row:
            raise TranscriptNotFound(id)
        return _row_to_response(row)

    async def soft_delete(self, id: UUID) -> TranscriptResponse:
        now = datetime.now(timezone.utc)
        # Single atomic statement: the business rule (not referenced by any
        # execution) lives in the WHERE clause.
        stmt = (
            update(transcripts)
            .where(
                transcripts.c.id == id,
                transcripts.c.is_deleted == False,  # noqa: E712
                ~exists(select(executions.c.id).where(executions.c.transcript_id == id)),
            )
            .values(is_deleted=True, deleted_at=now, updated_at=now)
            .returning(*transcripts.c)
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if not row:
            await self._session.rollback()
            current = await self._session.execute(
                select(transcripts.c.is_deleted).where(transcripts.c.id == id)
            )
            current_row = current.fetchone()
            if not current_row or current_row.is_deleted:
                raise TranscriptNotFound(id)
            raise TranscriptHasExecutions(id)
        await self._session.commit()
        return _row_to_response(row)
