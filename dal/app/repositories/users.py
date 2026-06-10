import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import roles, user_roles, users
from app.schemas.requests import UserCreate
from app.schemas.responses import UserResponse


def _row_to_response(row) -> UserResponse:
    return UserResponse(
        id=row.id,
        username=row.username,
        email=row.email,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class UsersRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: UserCreate) -> UserResponse:
        now = datetime.now(timezone.utc)
        row_id = uuid.uuid4()
        stmt = users.insert().values(
            id=row_id,
            username=data.username,
            email=data.email.lower(),
            is_active=data.is_active,
            created_at=now,
            updated_at=now,
        ).returning(*users.c)
        try:
            result = await self._session.execute(stmt)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise
        return _row_to_response(result.fetchone())

    async def get_by_id(self, id: UUID) -> UserResponse | None:
        stmt = select(users).where(users.c.id == id)
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def get_by_email(self, email: str) -> UserResponse | None:
        stmt = select(users).where(func.lower(users.c.email) == email.strip().lower())
        result = await self._session.execute(stmt)
        row = result.fetchone()
        return _row_to_response(row) if row else None

    async def assign_role(self, user_id: UUID, role_id: UUID) -> None:
        # Validate both exist before inserting
        user_check = await self._session.execute(select(users.c.id).where(users.c.id == user_id))
        if not user_check.fetchone():
            raise ValueError(f"User {user_id} not found")
        role_check = await self._session.execute(select(roles.c.id).where(roles.c.id == role_id))
        if not role_check.fetchone():
            raise ValueError(f"Role {role_id} not found")

        stmt = user_roles.insert().values(user_id=user_id, role_id=role_id)
        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise
