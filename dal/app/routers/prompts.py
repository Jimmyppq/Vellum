import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.errors import (
    InvalidStateTransition,
    PromptHasExecutions,
    PromptNotFound,
)
from app.repositories.prompt_versions import PromptVersionsRepository
from app.repositories.prompts import PromptsRepository
from app.schemas.requests import PromptCreate, PromptStatusUpdate, VersionCreate
from app.schemas.responses import (
    PromptResponse,
    ResponseMeta,
    SuccessResponse,
    VersionResponse,
)

router = APIRouter(prefix="/v1/prompts", tags=["prompts"])


def _meta(request_id: str | None = None) -> ResponseMeta:
    return ResponseMeta(request_id=request_id or str(uuid.uuid4()))


async def _ensure_prompt_visible(session: AsyncSession, id: UUID) -> None:
    """Subresources of a soft-deleted (or missing) prompt are 404."""
    repo = PromptsRepository(session)
    prompt = await repo.get_by_id(id)
    if not prompt:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Prompt {id} not found"})


@router.post("", status_code=201, response_model=SuccessResponse[PromptResponse])
async def create_prompt(body: PromptCreate, session: AsyncSession = Depends(get_session)):
    repo = PromptsRepository(session)
    prompt = await repo.create(body)
    return SuccessResponse(data=prompt, meta=_meta())


@router.get("/{id}", response_model=SuccessResponse[PromptResponse])
async def get_prompt(
    id: UUID,
    include_deleted: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    repo = PromptsRepository(session)
    prompt = await repo.get_by_id(id, include_deleted=include_deleted)
    if not prompt:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Prompt {id} not found"})
    return SuccessResponse(data=prompt, meta=_meta())


@router.get("", response_model=SuccessResponse[list[PromptResponse]])
async def list_prompts(
    status: str | None = Query(None),
    owner_id: UUID | None = Query(None),
    include_deleted: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = PromptsRepository(session)
    items = await repo.list(
        status=status, owner_id=owner_id, limit=limit, offset=offset,
        include_deleted=include_deleted,
    )
    return SuccessResponse(data=items, meta=_meta())


@router.patch("/{id}/status", response_model=SuccessResponse[PromptResponse])
async def update_prompt_status(id: UUID, body: PromptStatusUpdate, session: AsyncSession = Depends(get_session)):
    repo = PromptsRepository(session)
    try:
        prompt = await repo.update_status(id, body.status)
    except PromptNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATE_TRANSITION", "message": str(exc)},
        )
    return SuccessResponse(data=prompt, meta=_meta())


@router.delete("/{id}", response_model=SuccessResponse[PromptResponse])
async def delete_prompt(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = PromptsRepository(session)
    try:
        prompt = await repo.soft_delete(id)
    except PromptNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    except PromptHasExecutions as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "PROMPT_HAS_EXECUTIONS", "message": str(exc)},
        )
    return SuccessResponse(data=prompt, meta=_meta())


# --- Versions ---

@router.post("/{id}/versions", status_code=201, response_model=SuccessResponse[VersionResponse])
async def create_version(id: UUID, body: VersionCreate, session: AsyncSession = Depends(get_session)):
    await _ensure_prompt_visible(session, id)
    body = body.model_copy(update={"prompt_id": id})
    repo = PromptVersionsRepository(session)
    version = await repo.create(body)
    return SuccessResponse(data=version, meta=_meta())


@router.get("/{id}/versions", response_model=SuccessResponse[list[VersionResponse]])
async def list_versions(id: UUID, session: AsyncSession = Depends(get_session)):
    await _ensure_prompt_visible(session, id)
    repo = PromptVersionsRepository(session)
    items = await repo.list_by_prompt(id)
    return SuccessResponse(data=items, meta=_meta())


@router.get("/{id}/versions/active", response_model=SuccessResponse[VersionResponse])
async def get_active_version(id: UUID, session: AsyncSession = Depends(get_session)):
    await _ensure_prompt_visible(session, id)
    repo = PromptVersionsRepository(session)
    version = await repo.get_active(id)
    if not version:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "No active version found"})
    return SuccessResponse(data=version, meta=_meta())


@router.get("/{id}/versions/{version_id}", response_model=SuccessResponse[VersionResponse])
async def get_version(id: UUID, version_id: UUID, session: AsyncSession = Depends(get_session)):
    await _ensure_prompt_visible(session, id)
    repo = PromptVersionsRepository(session)
    version = await repo.get_by_id(version_id)
    if not version or version.prompt_id != id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Version {version_id} not found"})
    return SuccessResponse(data=version, meta=_meta())
