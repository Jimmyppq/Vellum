import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.users import UsersRepository
from app.schemas.requests import RoleAssign, UserCreate
from app.schemas.responses import ResponseMeta, SuccessResponse, UserResponse

router = APIRouter(prefix="/v1/users", tags=["users"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=str(uuid.uuid4()))


@router.post("", status_code=201, response_model=SuccessResponse[UserResponse])
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_session)):
    repo = UsersRepository(session)
    try:
        user = await repo.create(body)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail={"code": "USER_EMAIL_CONFLICT", "message": "Email already registered"},
        )
    return SuccessResponse(data=user, meta=_meta())


@router.get("/{id}", response_model=SuccessResponse[UserResponse])
async def get_user(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = UsersRepository(session)
    user = await repo.get_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"User {id} not found"})
    return SuccessResponse(data=user, meta=_meta())


@router.get("/email/{email}", response_model=SuccessResponse[UserResponse])
async def get_user_by_email(email: str, session: AsyncSession = Depends(get_session)):
    repo = UsersRepository(session)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"User with email {email} not found"})
    return SuccessResponse(data=user, meta=_meta())


@router.post("/{id}/roles", response_model=SuccessResponse[dict])
async def assign_role(id: UUID, body: RoleAssign, session: AsyncSession = Depends(get_session)):
    repo = UsersRepository(session)
    try:
        await repo.assign_role(id, body.role_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc)})
    except IntegrityError:
        raise HTTPException(status_code=409, detail={"code": "ROLE_ALREADY_ASSIGNED", "message": "Role already assigned"})
    return SuccessResponse(data={"assigned": True}, meta=_meta())
