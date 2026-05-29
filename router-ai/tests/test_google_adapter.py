import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.google import GoogleAdapter
from app.models.request import MessageRequest, EmbedRequest
from app.models.common import Message


def make_adapter():
    with patch("app.adapters.google.genai.Client"):
        adapter = GoogleAdapter(api_key="fake-key")
    return adapter


def mock_generate_response(text="respuesta de prueba", input_tokens=10, output_tokens=20):
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata.prompt_token_count = input_tokens
    resp.usage_metadata.candidates_token_count = output_tokens
    return resp


def async_chunks(items):
    async def _gen():
        for item in items:
            yield item
    return _gen()


def make_stream_chunks(texts, input_tokens=5, output_tokens=8):
    chunks = []
    for text in texts:
        c = MagicMock()
        c.text = text
        c.usage_metadata = None
        chunks.append(c)
    final = MagicMock()
    final.text = None
    final.usage_metadata.prompt_token_count = input_tokens
    final.usage_metadata.candidates_token_count = output_tokens
    chunks.append(final)
    return chunks


# ── message() ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_retorna_respuesta_correcta():
    adapter = make_adapter()
    adapter._client.aio.models.generate_content = AsyncMock(
        return_value=mock_generate_response("hola mundo", input_tokens=10, output_tokens=5)
    )
    request = MessageRequest(
        provider="google",
        messages=[Message(role="user", content="¿Qué es Python?")],
    )
    response = await adapter.message(request)

    assert response.provider == "google"
    assert response.content == "hola mundo"
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5


@pytest.mark.asyncio
async def test_message_usa_modelo_default():
    adapter = make_adapter()
    adapter._client.aio.models.generate_content = AsyncMock(
        return_value=mock_generate_response()
    )
    request = MessageRequest(
        provider="google",
        messages=[Message(role="user", content="Hola")],
    )
    await adapter.message(request)

    call_kwargs = adapter._client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_message_usa_modelo_explicito():
    adapter = make_adapter()
    adapter._client.aio.models.generate_content = AsyncMock(
        return_value=mock_generate_response()
    )
    request = MessageRequest(
        provider="google",
        model="gemini-1.5-pro",
        messages=[Message(role="user", content="Hola")],
    )
    await adapter.message(request)

    call_kwargs = adapter._client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-1.5-pro"


@pytest.mark.asyncio
async def test_message_mapea_rol_assistant_a_model():
    adapter = make_adapter()
    adapter._client.aio.models.generate_content = AsyncMock(
        return_value=mock_generate_response()
    )
    request = MessageRequest(
        provider="google",
        messages=[
            Message(role="user", content="¿Cuál es la capital de Francia?"),
            Message(role="assistant", content="París."),
            Message(role="user", content="¿Y de Italia?"),
        ],
    )
    await adapter.message(request)

    call_kwargs = adapter._client.aio.models.generate_content.call_args.kwargs
    roles = [c.role for c in call_kwargs["contents"]]
    assert roles == ["user", "model", "user"]


# ── stream() ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_emite_chunks_de_texto():
    adapter = make_adapter()
    chunks = make_stream_chunks(["Hola", " mundo"])
    adapter._client.aio.models.generate_content_stream = AsyncMock(
        return_value=async_chunks(chunks)
    )
    request = MessageRequest(
        provider="google",
        messages=[Message(role="user", content="Di hola")],
    )
    results = [chunk async for chunk in adapter.stream(request)]

    text_chunks = [c for c in results if not c.done]
    assert len(text_chunks) == 2
    assert text_chunks[0].delta == "Hola"
    assert text_chunks[1].delta == " mundo"


@pytest.mark.asyncio
async def test_stream_chunk_final_tiene_done_true_y_usage():
    adapter = make_adapter()
    chunks = make_stream_chunks(["texto"], input_tokens=7, output_tokens=3)
    adapter._client.aio.models.generate_content_stream = AsyncMock(
        return_value=async_chunks(chunks)
    )
    request = MessageRequest(
        provider="google",
        messages=[Message(role="user", content="Hola")],
    )
    results = [chunk async for chunk in adapter.stream(request)]

    final = results[-1]
    assert final.done is True
    assert final.usage.input_tokens == 7
    assert final.usage.output_tokens == 3


@pytest.mark.asyncio
async def test_stream_usa_modelo_default():
    adapter = make_adapter()
    chunks = make_stream_chunks(["ok"])
    adapter._client.aio.models.generate_content_stream = AsyncMock(
        return_value=async_chunks(chunks)
    )
    request = MessageRequest(
        provider="google",
        messages=[Message(role="user", content="Hola")],
    )
    async for _ in adapter.stream(request):
        pass

    call_kwargs = adapter._client.aio.models.generate_content_stream.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.0-flash"


# ── embed() ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_input_unico():
    adapter = make_adapter()
    emb = MagicMock()
    emb.values = [0.1, 0.2, 0.3]
    adapter._client.aio.models.embed_content = AsyncMock(
        return_value=MagicMock(embeddings=[emb])
    )
    request = EmbedRequest(provider="google", input="texto de prueba")
    response = await adapter.embed(request)

    assert response.provider == "google"
    assert len(response.embeddings) == 1
    assert response.embeddings[0] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_input_lista():
    adapter = make_adapter()
    emb1, emb2 = MagicMock(), MagicMock()
    emb1.values = [0.1, 0.2]
    emb2.values = [0.3, 0.4]
    adapter._client.aio.models.embed_content = AsyncMock(
        return_value=MagicMock(embeddings=[emb1, emb2])
    )
    request = EmbedRequest(provider="google", input=["texto uno", "texto dos"])
    response = await adapter.embed(request)

    assert len(response.embeddings) == 2


@pytest.mark.asyncio
async def test_embed_usa_modelo_default():
    adapter = make_adapter()
    emb = MagicMock()
    emb.values = [0.5]
    adapter._client.aio.models.embed_content = AsyncMock(
        return_value=MagicMock(embeddings=[emb])
    )
    request = EmbedRequest(provider="google", input="texto")
    await adapter.embed(request)

    call_kwargs = adapter._client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-004"


# ── health() ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_ok():
    adapter = make_adapter()
    adapter._client.aio.models.list = AsyncMock(return_value=MagicMock())
    result = await adapter.health()
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_timeout():
    adapter = make_adapter()
    adapter._client.aio.models.list = AsyncMock(side_effect=asyncio.TimeoutError())
    result = await adapter.health()
    assert result["status"] == "error"
    assert result["detail"] == "timeout"


@pytest.mark.asyncio
async def test_health_error_de_api():
    adapter = make_adapter()
    adapter._client.aio.models.list = AsyncMock(
        side_effect=Exception("invalid API key")
    )
    result = await adapter.health()
    assert result["status"] == "error"
    assert "invalid API key" in result["detail"]
