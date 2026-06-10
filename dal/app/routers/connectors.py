import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.connectors import ConnectorsRepository
from app.schemas.requests import ConnectorActiveUpdate, ConnectorCreate
from app.schemas.responses import ConnectorResponse, ResponseMeta, SuccessResponse

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=str(uuid.uuid4()))


@router.post("", status_code=201, response_model=SuccessResponse[ConnectorResponse])
async def create_connector(body: ConnectorCreate, session: AsyncSession = Depends(get_session)):
    repo = ConnectorsRepository(session)
    connector = await repo.create(body)
    return SuccessResponse(data=connector, meta=_meta())


@router.get("", response_model=SuccessResponse[list[ConnectorResponse]])
async def list_connectors(session: AsyncSession = Depends(get_session)):
    repo = ConnectorsRepository(session)
    items = await repo.list_active()
    return SuccessResponse(data=items, meta=_meta())


@router.get("/{id}", response_model=SuccessResponse[ConnectorResponse])
async def get_connector(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = ConnectorsRepository(session)
    connector = await repo.get_by_id(id)
    if not connector:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Connector {id} not found"})
    return SuccessResponse(data=connector, meta=_meta())


@router.patch("/{id}/active", response_model=SuccessResponse[ConnectorResponse])
async def update_connector_active(id: UUID, body: ConnectorActiveUpdate, session: AsyncSession = Depends(get_session)):
    repo = ConnectorsRepository(session)
    try:
        connector = await repo.set_active(id, body.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    return SuccessResponse(data=connector, meta=_meta())
