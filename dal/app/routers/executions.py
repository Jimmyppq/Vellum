import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.errors import (
    ExecutionNotFound,
    InvalidPayloadForTransition,
    InvalidStateTransition,
)
from app.repositories.executions import ExecutionsRepository
from app.schemas.requests import ExecutionCreate, ExecutionStatusUpdate
from app.schemas.responses import ExecutionResponse, ResponseMeta, SuccessResponse

router = APIRouter(prefix="/v1/executions", tags=["executions"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=str(uuid.uuid4()))


@router.post("", status_code=201, response_model=SuccessResponse[ExecutionResponse])
async def create_execution(body: ExecutionCreate, session: AsyncSession = Depends(get_session)):
    repo = ExecutionsRepository(session)
    execution = await repo.create(body)
    return SuccessResponse(data=execution, meta=_meta())


@router.get("/{id}", response_model=SuccessResponse[ExecutionResponse])
async def get_execution(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = ExecutionsRepository(session)
    execution = await repo.get_by_id(id)
    if not execution:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Execution {id} not found"})
    return SuccessResponse(data=execution, meta=_meta())


@router.patch("/{id}/status", response_model=SuccessResponse[ExecutionResponse])
async def update_execution_status(id: UUID, body: ExecutionStatusUpdate, session: AsyncSession = Depends(get_session)):
    repo = ExecutionsRepository(session)
    try:
        execution = await repo.update_status(id, body.status, body.output_data, body.cost)
    except InvalidPayloadForTransition as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PAYLOAD_FOR_TRANSITION", "message": str(exc)},
        )
    except ExecutionNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATE_TRANSITION", "message": str(exc)},
        )
    return SuccessResponse(data=execution, meta=_meta())


@router.get("", response_model=SuccessResponse[list[ExecutionResponse]])
async def list_executions(
    prompt_id: UUID | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = ExecutionsRepository(session)
    if prompt_id:
        items = await repo.list_by_prompt(prompt_id, limit=limit, offset=offset)
    else:
        items = []
    return SuccessResponse(data=items, meta=_meta())
