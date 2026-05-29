from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
