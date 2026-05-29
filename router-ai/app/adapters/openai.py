import asyncio
from typing import AsyncGenerator
import openai
from app.adapters.base import BaseAdapter
from app.models.request import MessageRequest, EmbedRequest
from app.models.response import MessageResponse, EmbedResponse, StreamChunk
from app.models.common import UsageInfo


class OpenAIAdapter(BaseAdapter):

    def __init__(self, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def message(self, request: MessageRequest) -> MessageResponse:
        model = request.model or "gpt-4o"
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        extra = request.options or {}

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            **extra,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return MessageResponse(
            provider="openai",
            model=response.model,
            content=content,
            usage=UsageInfo(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            ),
        )

    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]:
        model = request.model or "gpt-4o"
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        extra = request.options or {}

        input_tokens = 0
        output_tokens = 0
        async with await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            **extra,
        ) as stream:
            async for chunk in stream:
                if chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(delta=chunk.choices[0].delta.content, done=False)

        yield StreamChunk(
            done=True,
            usage=UsageInfo(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        model = request.model or "text-embedding-3-small"
        inputs = request.input if isinstance(request.input, list) else [request.input]
        response = await self._client.embeddings.create(model=model, input=inputs)
        usage = response.usage
        return EmbedResponse(
            provider="openai",
            model=response.model,
            embeddings=[item.embedding for item in response.data],
            usage=UsageInfo(input_tokens=usage.prompt_tokens if usage else 0),
        )

    async def health(self) -> dict:
        try:
            await asyncio.wait_for(self._client.models.list(), timeout=5.0)
            return {"status": "ok"}
        except asyncio.TimeoutError:
            return {"status": "error", "detail": "timeout"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
