import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import executions
from app.schemas.requests import ExecutionCreate
from app.schemas.responses import ExecutionResponse

TERMINAL_STATUSES = {"completed", "failed"}
VALID_STATUSES = {"queued", "running", "completed", "failed"}


def _row_to_response(row) -> ExecutionResponse:
    return ExecutionResponse(
        id=row.id,
        prompt_id=row.prompt_id,
        version_id=row.version_id,
        transcript_id=row.transcript_id,
        executed_by=row.executed_by,
        input_data=row.input_data,
        output_data=row.output_data,
        status=row.status,
        model_used=row.model_used,
        cost=row.cost,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


class ExecutionsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ExecutionCreate) -> ExecutionResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()
        stmt = executions.insert().values(
            id=row_id,
            prompt_id=data.prompt_id,
            version_id=data.version_id,
            transcript_id=data.transcript_id,
            executed_by=data.executed_by,
            input_data=data.input_data,
            output_data=None,
            status="queued",
            model_used=data.model_used,
            cost=None,
            created_at=now,
            completed_at=None,
        ).returning(*executions.c)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return _row_to_response(result.fetchone())

    async def get_by_id(self, id: UUID) -> ExecutionResponse | None:
        stmt = select(executions).where(executions.c.id == id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def update_status(
        self, id: UUID, status: str, output: dict[str, Any] | None = None
    ) -> ExecutionResponse:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")
        values: dict[str, Any] = {"status": status}
        if status in TERMINAL_STATUSES:
            values["completed_at"] = datetime.now(timezone.utc)
        if output is not None:
            values["output_data"] = output
        stmt = (
            update(executions)
            .where(executions.c.id == id)
            .values(**values)
            .returning(*executions.c)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        row = result.fetchone()
        if not row:
            raise ValueError(f"Execution {id} not found")
        return _row_to_response(row)

    async def list_by_prompt(
        self, prompt_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[ExecutionResponse]:
        stmt = (
            select(executions)
            .where(executions.c.prompt_id == prompt_id)
            .order_by(executions.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [_row_to_response(row) for row in result.fetchall()]
