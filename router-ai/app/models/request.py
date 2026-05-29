from typing import Any
from pydantic import BaseModel, field_validator
from app.models.common import Message


class MessageRequest(BaseModel):
    provider: str
    model: str | None = None
    messages: list[Message]
    options: dict[str, Any] | None = None

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        v = str(v).strip().lower()
        if not v:
            raise ValueError("provider no puede estar vacío")
        return v

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: list[Message]) -> list[Message]:
        if not v:
            raise ValueError("messages debe contener al menos un mensaje")
        return v


class EmbedRequest(BaseModel):
    provider: str
    model: str | None = None
    input: str | list[str]

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        v = str(v).strip().lower()
        if not v:
            raise ValueError("provider no puede estar vacío")
        return v

    @field_validator("input")
    @classmethod
    def validate_input(cls, v: str | list[str]) -> str | list[str]:
        if isinstance(v, list):
            if not v:
                raise ValueError("input no puede ser una lista vacía")
        elif not str(v).strip():
            raise ValueError("input no puede estar vacío")
        return v
