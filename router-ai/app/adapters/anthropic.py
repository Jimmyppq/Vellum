import asyncio
from typing import AsyncGenerator
import anthropic
from app.adapters.base import BaseAdapter
from app.models.request import MessageRequest, EmbedRequest
from app.models.response import MessageResponse, EmbedResponse, StreamChunk
from app.models.common import UsageInfo


class AnthropicAdapter(BaseAdapter):

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def message(self, request: MessageRequest) -> MessageResponse:
        model = request.model or "claude-3-5-sonnet-20241022"
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        extra = request.options or {}

        response = await self._client.messages.create(
            model=model,
            max_tokens=extra.pop("max_tokens", 4096),
            messages=messages,
            **extra,
        )
        content = response.content[0].text if response.content else ""
        return MessageResponse(
            provider="anthropic",
            model=response.model,
            content=content,
            usage=UsageInfo(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )

    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]:
        model = request.model or "claude-3-5-sonnet-20241022"
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        extra = request.options or {}

        async with self._client.messages.stream(
            model=model,
            max_tokens=extra.pop("max_tokens", 4096),
            messages=messages,
            **extra,
        ) as stream:
            async for text in stream.text_stream:
                yield StreamChunk(delta=text, done=False)
            final = await stream.get_final_message()
            yield StreamChunk(
                done=True,
                usage=UsageInfo(
                    input_tokens=final.usage.input_tokens,
                    output_tokens=final.usage.output_tokens,
                ),
            )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        raise NotImplementedError("CAPABILITY_NOT_SUPPORTED")

    async def health(self) -> dict:
        try:
            await asyncio.wait_for(self._client.models.list(), timeout=5.0)
            return {"status": "ok"}
        except asyncio.TimeoutError:
            return {"status": "error", "detail": "timeout"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
