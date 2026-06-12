from typing import Any
from pydantic import BaseModel
from app.models.common import UsageInfo

APP_VERSION = "0.2.0"


class Meta(BaseModel):
    request_id: str
    version: str = APP_VERSION


class ApiResponse(BaseModel):
    data: Any
    meta: Meta


class MessageResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: UsageInfo


class EmbedResponse(BaseModel):
    provider: str
    model: str
    embeddings: list[list[float]]
    usage: UsageInfo


class StreamChunk(BaseModel):
    delta: str = ""
    done: bool = False
    usage: UsageInfo | None = None
    error: bool = False
    code: str | None = None
    message: str | None = None


class ProviderStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None
    circuit: str | None = None  # closed | open | half_open


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, str]
    rate_limit_store: str = "memory"


class ErrorResponse(BaseModel):
    code: str
    message: str
    trace_id: str | None = None
    provider: str | None = None
    # Solo en errores temporales (429, 503); coincide con el header Retry-After
    retry_after_seconds: int | None = None
