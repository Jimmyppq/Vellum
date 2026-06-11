import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.errors import TranscriptHasExecutions, TranscriptNotFound
from app.repositories.transcript_versions import TranscriptVersionsRepository
from app.repositories.transcripts import TranscriptsRepository
from app.schemas.requests import (
    TranscriptCreate,
    TranscriptStatusUpdate,
    TranscriptVersionCreate,
)
from app.schemas.responses import (
    ResponseMeta,
    SuccessResponse,
    TranscriptResponse,
    TranscriptVersionResponse,
)

router = APIRouter(prefix="/v1/transcripts", tags=["transcripts"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=str(uuid.uuid4()))


async def _ensure_transcript_visible(session: AsyncSession, id: UUID) -> None:
    """Subresources of a soft-deleted (or missing) transcript are 404."""
    repo = TranscriptsRepository(session)
    transcript = await repo.get_by_id(id)
    if not transcript:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Transcript {id} not found"})


@router.post("", status_code=201, response_model=SuccessResponse[TranscriptResponse])
async def create_transcript(body: TranscriptCreate, session: AsyncSession = Depends(get_session)):
    repo = TranscriptsRepository(session)
    transcript = await repo.create(body)
    return SuccessResponse(data=transcript, meta=_meta())


@router.get("/{id}", response_model=SuccessResponse[TranscriptResponse])
async def get_transcript(
    id: UUID,
    include_deleted: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    repo = TranscriptsRepository(session)
    transcript = await repo.get_by_id(id, include_deleted=include_deleted)
    if not transcript:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Transcript {id} not found"})
    return SuccessResponse(data=transcript, meta=_meta())


@router.patch("/{id}/status", response_model=SuccessResponse[TranscriptResponse])
async def update_transcript_status(id: UUID, body: TranscriptStatusUpdate, session: AsyncSession = Depends(get_session)):
    repo = TranscriptsRepository(session)
    try:
        transcript = await repo.update_status(id, body.status)
    except (TranscriptNotFound, ValueError) as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    return SuccessResponse(data=transcript, meta=_meta())


@router.delete("/{id}", response_model=SuccessResponse[TranscriptResponse])
async def delete_transcript(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = TranscriptsRepository(session)
    try:
        transcript = await repo.soft_delete(id)
    except TranscriptNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    except TranscriptHasExecutions as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "TRANSCRIPT_HAS_EXECUTIONS", "message": str(exc)},
        )
    return SuccessResponse(data=transcript, meta=_meta())


@router.post("/{id}/versions", status_code=201, response_model=SuccessResponse[TranscriptVersionResponse])
async def create_transcript_version(id: UUID, body: TranscriptVersionCreate, session: AsyncSession = Depends(get_session)):
    await _ensure_transcript_visible(session, id)
    body = body.model_copy(update={"transcript_id": id})
    repo = TranscriptVersionsRepository(session)
    version = await repo.create(body)
    return SuccessResponse(data=version, meta=_meta())


@router.get("/{id}/versions/active", response_model=SuccessResponse[TranscriptVersionResponse])
async def get_active_transcript_version(id: UUID, session: AsyncSession = Depends(get_session)):
    await _ensure_transcript_visible(session, id)
    repo = TranscriptVersionsRepository(session)
    version = await repo.get_active(id)
    if not version:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "No active version found"})
    return SuccessResponse(data=version, meta=_meta())
