from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Standard response envelope
# ---------------------------------------------------------------------------

class ResponseMeta(BaseModel):
    request_id: str
    version: str = "1.0.0"


class SuccessResponse(BaseModel, Generic[T]):
    data: T
    meta: ResponseMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    trace_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Entity responses
# ---------------------------------------------------------------------------

class PromptResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    status: str
    visibility: str
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VersionResponse(BaseModel):
    id: UUID
    prompt_id: UUID
    version_number: int
    content: str
    change_log: str | None
    created_by: UUID
    created_at: datetime
    is_active: bool


class ExecutionResponse(BaseModel):
    id: UUID
    prompt_id: UUID
    version_id: UUID
    transcript_id: UUID | None
    executed_by: UUID
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    status: str
    model_used: str | None
    cost: Decimal | None
    created_at: datetime
    completed_at: datetime | None


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TranscriptResponse(BaseModel):
    id: UUID
    name: str
    media_url: str | None
    owner_id: UUID
    status: str
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TranscriptVersionResponse(BaseModel):
    id: UUID
    transcript_id: UUID
    version_number: int
    content: str
    change_log: str | None
    created_by: UUID
    created_at: datetime
    is_active: bool


class ConnectorResponse(BaseModel):
    id: UUID
    type: str
    name: str
    is_active: bool
    created_at: datetime


class SystemConfigResponse(BaseModel):
    key: str
    value: Any
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    db: bool
    service: str = "dal"
    version: str = "1.0.0"
