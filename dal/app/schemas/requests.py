from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class PromptCreate(BaseModel):
    name: str
    description: str | None = None
    owner_id: UUID
    visibility: Literal["private", "public", "team"] = "private"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v


class PromptStatusUpdate(BaseModel):
    status: Literal["draft", "approved", "deprecated"]


class VersionCreate(BaseModel):
    prompt_id: UUID | None = None  # set by the router from the URL path parameter
    content: str
    change_log: str | None = None
    created_by: UUID
    is_active: bool = False

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class ExecutionCreate(BaseModel):
    prompt_id: UUID
    version_id: UUID
    transcript_id: UUID | None = None
    executed_by: UUID
    input_data: dict[str, Any]
    model_used: str | None = None


class ExecutionStatusUpdate(BaseModel):
    status: Literal["queued", "running", "completed", "failed"]
    output_data: dict[str, Any] | None = None


class UserCreate(BaseModel):
    username: str
    email: str
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("invalid email format")
        return v

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("username must not be empty")
        return v


class RoleAssign(BaseModel):
    role_id: UUID


class TranscriptCreate(BaseModel):
    name: str
    media_url: str | None = None
    owner_id: UUID
    status: str = "pending"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v


class TranscriptStatusUpdate(BaseModel):
    status: str


class TranscriptVersionCreate(BaseModel):
    transcript_id: UUID | None = None  # set by the router from the URL path parameter
    content: str
    change_log: str | None = None
    created_by: UUID
    is_active: bool = False

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class ConnectorCreate(BaseModel):
    type: str
    name: str
    is_active: bool = True

    @field_validator("type", "name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty")
        return v


class ConnectorActiveUpdate(BaseModel):
    is_active: bool


class SystemConfigUpdate(BaseModel):
    value: Any
