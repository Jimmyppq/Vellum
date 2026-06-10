import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.schema import system_config
from app.schemas.requests import SystemConfigUpdate
from app.schemas.responses import ResponseMeta, SuccessResponse, SystemConfigResponse

router = APIRouter(prefix="/v1/config", tags=["config"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=str(uuid.uuid4()))


@router.get("", response_model=SuccessResponse[list[SystemConfigResponse]])
async def get_config(session: AsyncSession = Depends(get_session)):
    stmt = select(system_config).order_by(system_config.c.key)
    result = await session.execute(stmt)
    items = [
        SystemConfigResponse(key=row.key, value=row.value, updated_at=row.updated_at)
        for row in result.fetchall()
    ]
    return SuccessResponse(data=items, meta=_meta())


@router.put("/{key}", response_model=SuccessResponse[SystemConfigResponse])
async def set_config(key: str, body: SystemConfigUpdate, session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    # Upsert via insert with on_conflict_do_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = (
        pg_insert(system_config)
        .values(key=key, value=body.value, updated_at=now)
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": body.value, "updated_at": now},
        )
        .returning(*system_config.c)
    )
    result = await session.execute(stmt)
    await session.commit()
    row = result.fetchone()
    return SuccessResponse(
        data=SystemConfigResponse(key=row.key, value=row.value, updated_at=row.updated_at),
        meta=_meta(),
    )
