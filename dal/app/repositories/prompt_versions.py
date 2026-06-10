import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import prompt_versions
from app.schemas.requests import VersionCreate
from app.schemas.responses import VersionResponse


def _row_to_response(row) -> VersionResponse:
    return VersionResponse(
        id=row.id,
        prompt_id=row.prompt_id,
        version_number=row.version_number,
        content=row.content,
        change_log=row.change_log,
        created_by=row.created_by,
        created_at=row.created_at,
        is_active=row.is_active,
    )


class PromptVersionsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: VersionCreate) -> VersionResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()

        # Compute next version number
        from sqlalchemy import func
        max_stmt = select(func.max(prompt_versions.c.version_number)).where(
            prompt_versions.c.prompt_id == data.prompt_id
        )
        max_result = await self._session.execute(max_stmt)
        max_version = max_result.scalar() or 0

        if data.is_active:
            # Deactivate all previous versions atomically in the same transaction
            await self._deactivate_all_in_tx(data.prompt_id)

        stmt = prompt_versions.insert().values(
            id=row_id,
            prompt_id=data.prompt_id,
            version_number=max_version + 1,
            content=data.content,
            change_log=data.change_log,
            created_by=data.created_by,
            created_at=now,
            is_active=data.is_active,
        ).returning(*prompt_versions.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def _deactivate_all_in_tx(self, prompt_id: UUID) -> None:
        stmt = (
            update(prompt_versions)
            .where(prompt_versions.c.prompt_id == prompt_id)
            .values(is_active=False)
        )
        await self._session.execute(stmt)

    async def deactivate_all(self, prompt_id: UUID) -> None:
        await self._deactivate_all_in_tx(prompt_id)
        await self._session.commit()

    async def get_by_id(self, id: UUID) -> VersionResponse | None:
        stmt = select(prompt_versions).where(prompt_versions.c.id == id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def list_by_prompt(self, prompt_id: UUID) -> list[VersionResponse]:
        stmt = (
            select(prompt_versions)
            .where(prompt_versions.c.prompt_id == prompt_id)
            .order_by(prompt_versions.c.version_number.asc())
        )
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]

    async def get_active(self, prompt_id: UUID) -> VersionResponse | None:
        stmt = select(prompt_versions).where(
            prompt_versions.c.prompt_id == prompt_id,
            prompt_versions.c.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None
