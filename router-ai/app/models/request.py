from typing import Any
from pydantic import BaseModel
from app.models.common import Message


class MessageRequest(BaseModel):
    provider: str
    model: str | None = None
    messages: list[Message]
    options: dict[str, Any] | None = None


class EmbedRequest(BaseModel):
    provider: str
    model: str | None = None
    input: str | list[str]
