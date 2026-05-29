import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.registry import registry
from app.middleware.rate_limit import set_limiter
from app.models.common import UsageInfo
from app.models.response import MessageResponse, EmbedResponse

API_KEY = "test-key-123"


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("ROUTER_AI_API_KEY", API_KEY)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("LOG_DIR", "/tmp/router-ai-tests")
    # Settings es un singleton cargado al importar; parchear la instancia directamente
    # para que verify_api_key compare contra API_KEY y no contra el valor del proceso.
    from app.core import config
    from pydantic import SecretStr
    monkeypatch.setattr(config.settings, "router_ai_api_key", SecretStr(API_KEY))


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    set_limiter(None)
    yield
    set_limiter(None)


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.message = AsyncMock(return_value=MessageResponse(
        provider="mock",
        model="mock-model",
        content="respuesta de prueba",
        usage=UsageInfo(input_tokens=10, output_tokens=20),
    ))

    async def fake_stream(req):
        from app.models.response import StreamChunk
        yield StreamChunk(delta="hola", done=False)
        yield StreamChunk(done=True, usage=UsageInfo(input_tokens=5, output_tokens=3))

    adapter.stream = fake_stream
    adapter.embed = AsyncMock(return_value=EmbedResponse(
        provider="mock",
        model="mock-embed",
        embeddings=[[0.1, 0.2, 0.3]],
        usage=UsageInfo(input_tokens=5),
    ))
    adapter.health = AsyncMock(return_value={"status": "ok"})
    return adapter


@pytest.fixture
def client(mock_adapter):
    registry._adapters.clear()
    registry.register("mock", mock_adapter)
    with TestClient(app, headers={"X-API-Key": API_KEY}) as c:
        # El lifespan puede registrar ollama/lmstudio; los eliminamos para tests aislados
        registry._adapters.clear()
        registry.register("mock", mock_adapter)
        yield c
    registry._adapters.clear()
