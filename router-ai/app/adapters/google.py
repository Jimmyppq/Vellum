import asyncio
from typing import AsyncGenerator
from google import genai
from google.genai import types
from app.adapters.base import BaseAdapter
from app.models.request import MessageRequest, EmbedRequest
from app.models.response import MessageResponse, EmbedResponse, StreamChunk
from app.models.common import UsageInfo

_DEFAULT_CHAT_MODEL = "gemini-2.0-flash"
_DEFAULT_EMBED_MODEL = "text-embedding-004"


class GoogleAdapter(BaseAdapter):

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def _build_contents(self, request: MessageRequest) -> list[types.Content]:
        contents = []
        for m in request.messages:
            role = "model" if m.role == "assistant" else m.role
            contents.append(types.Content(role=role, parts=[types.Part(text=m.content)]))
        return contents

    async def message(self, request: MessageRequest) -> MessageResponse:
        model = request.model or _DEFAULT_CHAT_MODEL
        extra = request.options or {}

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=self._build_contents(request),
            config=types.GenerateContentConfig(**extra) if extra else None,
        )
        content = response.text or ""
        usage = response.usage_metadata
        return MessageResponse(
            provider="google",
            model=model,
            content=content,
            usage=UsageInfo(
                input_tokens=usage.prompt_token_count or 0 if usage else 0,
                output_tokens=usage.candidates_token_count or 0 if usage else 0,
            ),
        )

    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]:
        model = request.model or _DEFAULT_CHAT_MODEL
        extra = request.options or {}

        input_tokens = 0
        output_tokens = 0
        stream = await self._client.aio.models.generate_content_stream(
            model=model,
            contents=self._build_contents(request),
            config=types.GenerateContentConfig(**extra) if extra else None,
        )
        async for chunk in stream:
            if chunk.usage_metadata:
                input_tokens = chunk.usage_metadata.prompt_token_count or 0
                output_tokens = chunk.usage_metadata.candidates_token_count or 0
            if chunk.text:
                yield StreamChunk(delta=chunk.text, done=False)

        yield StreamChunk(
            done=True,
            usage=UsageInfo(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        model = request.model or _DEFAULT_EMBED_MODEL
        inputs = request.input if isinstance(request.input, list) else [request.input]

        response = await self._client.aio.models.embed_content(
            model=model,
            contents=inputs,
        )
        embeddings = [e.values for e in response.embeddings] if response.embeddings else []
        return EmbedResponse(
            provider="google",
            model=model,
            embeddings=embeddings,
            usage=UsageInfo(input_tokens=0),
        )

    async def health(self) -> dict:
        try:
            await asyncio.wait_for(self._client.aio.models.list(), timeout=5.0)
            return {"status": "ok"}
        except asyncio.TimeoutError:
            return {"status": "error", "detail": "timeout"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
