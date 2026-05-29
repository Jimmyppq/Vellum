import json
from typing import AsyncGenerator
import httpx
from app.adapters.base import BaseAdapter
from app.models.request import MessageRequest, EmbedRequest
from app.models.response import MessageResponse, EmbedResponse, StreamChunk
from app.models.common import UsageInfo


class OllamaAdapter(BaseAdapter):

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url.rstrip("/")

    async def message(self, request: MessageRequest) -> MessageResponse:
        model = request.model or "llama3.2"
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            **(request.options or {}),
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["message"]["content"]
        return MessageResponse(
            provider="ollama",
            model=data.get("model", model),
            content=content,
            usage=UsageInfo(
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
            ),
        )

    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]:
        model = request.model or "llama3.2"
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
            **(request.options or {}),
        }
        input_tokens = 0
        output_tokens = 0
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("done"):
                        input_tokens = chunk.get("prompt_eval_count", 0)
                        output_tokens = chunk.get("eval_count", 0)
                        break
                    delta = chunk.get("message", {}).get("content", "")
                    if delta:
                        yield StreamChunk(delta=delta, done=False)

        yield StreamChunk(
            done=True,
            usage=UsageInfo(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        model = request.model or "nomic-embed-text"
        inputs = request.input if isinstance(request.input, list) else [request.input]
        embeddings = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for text in inputs:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])

        return EmbedResponse(
            provider="ollama",
            model=model,
            embeddings=embeddings,
            usage=UsageInfo(),
        )

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
            return {"status": "ok"}
        except httpx.ConnectError:
            return {"status": "error", "detail": "Ollama no disponible"}
        except httpx.TimeoutException:
            return {"status": "error", "detail": "timeout"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
