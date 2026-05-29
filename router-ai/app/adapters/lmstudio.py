import json
from typing import AsyncGenerator
import httpx
from app.adapters.base import BaseAdapter
from app.models.request import MessageRequest, EmbedRequest
from app.models.response import MessageResponse, EmbedResponse, StreamChunk
from app.models.common import UsageInfo

_HEADERS = {"Content-Type": "application/json"}


class LMStudioAdapter(BaseAdapter):
    """Adaptador para LM Studio — API local compatible con el protocolo OpenAI."""

    def __init__(self, base_url: str = "http://localhost:1234/v1") -> None:
        self._base_url = base_url.rstrip("/")

    async def message(self, request: MessageRequest) -> MessageResponse:
        model = request.model or "local-model"
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            **(request.options or {}),
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=_HEADERS,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return MessageResponse(
            provider="lmstudio",
            model=data.get("model", model),
            content=content,
            usage=UsageInfo(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            ),
        )

    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]:
        model = request.model or "local-model"
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
            **(request.options or {}),
        }
        input_tokens = 0
        output_tokens = 0
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=_HEADERS,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    chunk = json.loads(raw)
                    if chunk.get("usage"):
                        input_tokens = chunk["usage"].get("prompt_tokens", 0)
                        output_tokens = chunk["usage"].get("completion_tokens", 0)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield StreamChunk(delta=delta, done=False)

        yield StreamChunk(
            done=True,
            usage=UsageInfo(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        model = request.model or "local-embedding-model"
        inputs = request.input if isinstance(request.input, list) else [request.input]
        payload = {"model": model, "input": inputs}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/embeddings",
                headers=_HEADERS,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        usage = data.get("usage", {})
        return EmbedResponse(
            provider="lmstudio",
            model=data.get("model", model),
            embeddings=[item["embedding"] for item in data["data"]],
            usage=UsageInfo(input_tokens=usage.get("prompt_tokens", 0)),
        )

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models", headers=_HEADERS)
                response.raise_for_status()
            return {"status": "ok"}
        except httpx.ConnectError:
            return {"status": "error", "detail": "LM Studio no disponible"}
        except httpx.TimeoutException:
            return {"status": "error", "detail": "timeout"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
