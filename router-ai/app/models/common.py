from typing import Literal
from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
