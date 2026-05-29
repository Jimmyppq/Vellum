from abc import ABC, abstractmethod
from typing import AsyncGenerator
from app.models.request import MessageRequest, EmbedRequest
from app.models.response import MessageResponse, EmbedResponse, StreamChunk


class BaseAdapter(ABC):

    @abstractmethod
    async def message(self, request: MessageRequest) -> MessageResponse:
        ...

    @abstractmethod
    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]:
        ...

    @abstractmethod
    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        ...

    @abstractmethod
    async def health(self) -> dict:
        ...
