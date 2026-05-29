from pydantic import BaseModel
from app.models.common import UsageInfo


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


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, str]


class ErrorResponse(BaseModel):
    code: str
    message: str
    provider: str | None = None
