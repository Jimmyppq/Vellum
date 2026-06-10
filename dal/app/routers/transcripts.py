import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
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


@router.post("", status_code=201, response_model=SuccessResponse[TranscriptResponse])
async def create_transcript(body: TranscriptCreate, session: AsyncSession = Depends(get_session)):
    repo = TranscriptsRepository(session)
    transcript = await repo.create(body)
    return SuccessResponse(data=transcript, meta=_meta())


@router.get("/{id}", response_model=SuccessResponse[TranscriptResponse])
async def get_transcript(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = TranscriptsRepository(session)
    transcript = await repo.get_by_id(id)
    if not transcript:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Transcript {id} not found"})
    return SuccessResponse(data=transcript, meta=_meta())


@router.patch("/{id}/status", response_model=SuccessResponse[TranscriptResponse])
async def update_transcript_status(id: UUID, body: TranscriptStatusUpdate, session: AsyncSession = Depends(get_session)):
    repo = TranscriptsRepository(session)
    try:
        transcript = await repo.update_status(id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    return SuccessResponse(data=transcript, meta=_meta())


@router.post("/{id}/versions", status_code=201, response_model=SuccessResponse[TranscriptVersionResponse])
async def create_transcript_version(id: UUID, body: TranscriptVersionCreate, session: AsyncSession = Depends(get_session)):
    body = body.model_copy(update={"transcript_id": id})
    repo = TranscriptVersionsRepository(session)
    version = await repo.create(body)
    return SuccessResponse(data=version, meta=_meta())


@router.get("/{id}/versions/active", response_model=SuccessResponse[TranscriptVersionResponse])
async def get_active_transcript_version(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = TranscriptVersionsRepository(session)
    version = await repo.get_active(id)
    if not version:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "No active version found"})
    return SuccessResponse(data=version, meta=_meta())
