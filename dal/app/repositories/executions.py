import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import executions
from app.repositories.errors import (
    ExecutionNotFound,
    InvalidPayloadForTransition,
    InvalidStateTransition,
)
from app.schemas.requests import ExecutionCreate
from app.schemas.responses import ExecutionResponse

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
# State machine: target status -> allowed source statuses. Any transition not
# listed here (including same -> same) is rejected. "queued" is never a valid
# target: executions only enter it on create.
ALLOWED_SOURCES = {
    "running": {"queued"},
    "completed": {"running"},
    "failed": {"running"},
    "cancelled": {"queued"},
}


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
        self,
        id: UUID,
        status: str,
        output: dict[str, Any] | None = None,
        cost: Decimal | None = None,
    ) -> ExecutionResponse:
        is_terminal = status in TERMINAL_STATUSES
        if not is_terminal:
            rejected = [
                name for name, value in (("output_data", output), ("cost", cost))
                if value is not None
            ]
            if rejected:
                raise InvalidPayloadForTransition(status, rejected)

        values: dict[str, Any] = {"status": status}
        if is_terminal:
            values["completed_at"] = datetime.now(timezone.utc)
            if output is not None:
                values["output_data"] = output
            if cost is not None:
                values["cost"] = cost

        # Atomic compare-and-set: the WHERE clause enforces the state machine,
        # so concurrent transitions can never both succeed.
        allowed_sources = ALLOWED_SOURCES.get(status, set())
        stmt = (
            update(executions)
            .where(executions.c.id == id, executions.c.status.in_(allowed_sources))
            .values(**values)
            .returning(*executions.c)
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if not row:
            await self._session.rollback()
            current = await self._session.execute(
                select(executions.c.status).where(executions.c.id == id)
            )
            current_row = current.fetchone()
            if not current_row:
                raise ExecutionNotFound(id)
            raise InvalidStateTransition(current_row.status, status)
        await self._session.commit()
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
