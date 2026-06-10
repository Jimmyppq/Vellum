import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import transcript_versions
from app.schemas.requests import TranscriptVersionCreate
from app.schemas.responses import TranscriptVersionResponse


def _row_to_response(row) -> TranscriptVersionResponse:
    return TranscriptVersionResponse(
        id=row.id,
        transcript_id=row.transcript_id,
        version_number=row.version_number,
        content=row.content,
        change_log=row.change_log,
        created_by=row.created_by,
        created_at=row.created_at,
        is_active=row.is_active,
    )


class TranscriptVersionsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TranscriptVersionCreate) -> TranscriptVersionResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()

        max_stmt = select(func.max(transcript_versions.c.version_number)).where(
            transcript_versions.c.transcript_id == data.transcript_id
        )
        max_result = await self._session.execute(max_stmt)
        max_version = max_result.scalar() or 0

        if data.is_active:
            await self._deactivate_all_in_tx(data.transcript_id)

        stmt = transcript_versions.insert().values(
            id=row_id,
            transcript_id=data.transcript_id,
            version_number=max_version + 1,
            content=data.content,
            change_log=data.change_log,
            created_by=data.created_by,
            created_at=now,
            is_active=data.is_active,
        ).returning(*transcript_versions.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def _deactivate_all_in_tx(self, transcript_id: UUID) -> None:
        stmt = (
            update(transcript_versions)
            .where(transcript_versions.c.transcript_id == transcript_id)
            .values(is_active=False)
        )
        await self._session.execute(stmt)

    async def deactivate_all(self, transcript_id: UUID) -> None:
        await self._deactivate_all_in_tx(transcript_id)
        await self._session.commit()

    async def get_by_id(self, id: UUID) -> TranscriptVersionResponse | None:
        stmt = select(transcript_versions).where(transcript_versions.c.id == id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def list_by_transcript(self, transcript_id: UUID) -> list[TranscriptVersionResponse]:
        stmt = (
            select(transcript_versions)
            .where(transcript_versions.c.transcript_id == transcript_id)
            .order_by(transcript_versions.c.version_number.asc())
        )
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]

    async def get_active(self, transcript_id: UUID) -> TranscriptVersionResponse | None:
        stmt = select(transcript_versions).where(
            transcript_versions.c.transcript_id == transcript_id,
            transcript_versions.c.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None
