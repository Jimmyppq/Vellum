# Correcciones router-ai — Guía de Ejecución Manual

**Auditoría basada en:** `CLAUDE.md` + `docs/doc_architecture.md`  
**Estado de C-1 (Google):** ya corregido en el código actual — no requiere acción.

---

## Orden de ejecución recomendado

```
Fix 3 → Fix 4 → Fix 1 → Fix 2+6 → Fix 5 → Fix 7 → Docs
```

Después de cada fix ejecuta:
```bash
cd router-ai
ROUTER_AI_API_KEY=test-key python -m pytest tests/ -v
```

---

## Fix 3 — B-2: Bug en `get_count` (falsos RATE_LIMIT_EXCEEDED)

**Archivo:** `router-ai/app/core/rate_limit_store.py`

`get_count` cuenta entradas sin evictar las expiradas. Reemplazar el archivo completo con:

```python
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque

WINDOW = 60


class RateLimitStore(ABC):

    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> int:
        ...

    @abstractmethod
    def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        ...

    @abstractmethod
    def oldest_timestamp(self, key: str) -> float | None:
        ...


class InMemoryRateLimitStore(RateLimitStore):

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def _evict(self, key: str, window_seconds: int) -> None:
        cutoff = time.monotonic() - window_seconds
        q = self._windows[key]
        while q and q[0] < cutoff:
            q.popleft()

    def increment(self, key: str, window_seconds: int) -> int:
        self._evict(key, window_seconds)
        self._windows[key].append(time.monotonic())
        return len(self._windows[key])

    def get_count(self, key: str, window_seconds: int = WINDOW) -> int:
        self._evict(key, window_seconds)
        return len(self._windows.get(key, deque()))

    def oldest_timestamp(self, key: str) -> float | None:
        q = self._windows.get(key)
        return q[0] if q else None
```

---

## Fix 4 — B-1: Validators Pydantic

### `router-ai/app/models/common.py`

```python
from typing import Literal
from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
```

### `router-ai/app/models/request.py`

```python
from typing import Any
from pydantic import BaseModel, field_validator
from app.models.common import Message


class MessageRequest(BaseModel):
    provider: str
    model: str | None = None
    messages: list[Message]
    options: dict[str, Any] | None = None

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        v = str(v).strip().lower()
        if not v:
            raise ValueError("provider no puede estar vacío")
        return v

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: list[Message]) -> list[Message]:
        if not v:
            raise ValueError("messages debe contener al menos un mensaje")
        return v


class EmbedRequest(BaseModel):
    provider: str
    model: str | None = None
    input: str | list[str]

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        v = str(v).strip().lower()
        if not v:
            raise ValueError("provider no puede estar vacío")
        return v

    @field_validator("input")
    @classmethod
    def validate_input(cls, v: str | list[str]) -> str | list[str]:
        if isinstance(v, list):
            if not v:
                raise ValueError("input no puede ser una lista vacía")
        elif not str(v).strip():
            raise ValueError("input no puede estar vacío")
        return v
```

---

## Fix 1 — A-2: Propagación de X-Trace-Id (PREREQUISITO de Fix 5)

**Archivo:** `router-ai/app/middleware/logging.py`

```python
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("router-ai.audit")


class AuditLogMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        status_code = response.status_code
        log_level = logging.WARNING if status_code >= 400 else logging.INFO

        logger.log(
            log_level,
            "%s %s",
            request.method,
            request.url.path,
            extra={
                "request_id": request_id,
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        return response
```

---

## Fix 2+6 — M-2+A-1: Container no-root + soporte mTLS

### 1. Crear `router-ai/entrypoint.sh` (archivo nuevo)

```bash
#!/bin/sh
if [ "$MTLS_ENABLED" = "true" ]; then
  exec python -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --ssl-keyfile "$MTLS_KEY_PATH" \
    --ssl-certfile "$MTLS_CERT_PATH" \
    --ssl-ca-certs "$MTLS_CA_PATH"
else
  exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
```

### 2. `router-ai/Dockerfile` — reemplazar completo

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/deps -r requirements.txt

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/deps

RUN useradd -m -s /bin/sh appuser

WORKDIR /app

COPY --from=builder /build/deps /app/deps
COPY app/ /app/app/
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app

VOLUME ["/logs", "/app/config"]

EXPOSE 8000

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
```

### 3. `router-ai/app/core/config.py` — añadir sección mTLS al final de `Settings`

Añadir estas 4 líneas dentro de la clase `Settings`, después de `rate_limits_config`:

```python
    # mTLS (false en dev local, true en staging/producción)
    mtls_enabled: bool = False
    mtls_cert_path: str = "/certs/service.crt"
    mtls_key_path: str = "/certs/service.key"
    mtls_ca_path: str = "/certs/ca.crt"
```

### 4. `router-ai/.env.example` — añadir al final del archivo

```bash
# ── mTLS (staging / producción) ───────────────────────────────────────────────
# false en desarrollo local, true en staging y producción
MTLS_ENABLED=false
MTLS_CERT_PATH=/certs/service.crt
MTLS_KEY_PATH=/certs/service.key
MTLS_CA_PATH=/certs/ca.crt
```

### 5. `router-ai/docker-compose.yml` — añadir volumen de certificados

En la sección `volumes`, añadir la línea `- ./certs:/certs:ro`:

```yaml
    volumes:
      - ./logs:/logs
      - ./config:/app/config
      - ./certs:/certs:ro
```

---

## Fix 5 — A-3: Formato estándar de respuesta API

### `router-ai/app/models/response.py` — reemplazar completo

```python
from typing import Any
from pydantic import BaseModel
from app.models.common import UsageInfo

APP_VERSION = "0.1.0"


class Meta(BaseModel):
    request_id: str
    version: str = APP_VERSION


class ApiResponse(BaseModel):
    data: Any
    meta: Meta


class MessageResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: UsageInfo


class EmbedResponse(BaseModel):
    provider: str
    model: str
    embeddings: list[list[float]]
    usage: UsageInfo


class StreamChunk(BaseModel):
    delta: str = ""
    done: bool = False
    usage: UsageInfo | None = None
    error: bool = False
    code: str | None = None
    message: str | None = None


class ProviderStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, str]


class ErrorResponse(BaseModel):
    code: str
    message: str
    trace_id: str | None = None
    provider: str | None = None
```

### `router-ai/app/api/v1/chat.py` — reemplazar completo

```python
import uuid
from fastapi import APIRouter, HTTPException, Request, status
from app.models.request import MessageRequest
from app.models.response import ApiResponse, Meta, MessageResponse, ErrorResponse
from app.core.registry import registry

router = APIRouter()


@router.post("/message", response_model=ApiResponse)
async def message(request: MessageRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", str(uuid.uuid4()))
    trace_id = getattr(http_request.state, "trace_id", None)

    adapter = registry.get(request.provider)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorResponse(
                code="PROVIDER_NOT_FOUND",
                message=f"Proveedor '{request.provider}' no está registrado.",
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
    try:
        result: MessageResponse = await adapter.message(request)
        registry.record_success(request.provider)
        return ApiResponse(data=result.model_dump(), meta=Meta(request_id=request_id))
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                code="CAPABILITY_NOT_SUPPORTED",
                message="Este proveedor no soporta esta operación.",
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
    except Exception as e:
        registry.record_failure(request.provider)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                code="PROVIDER_ERROR",
                message=str(e),
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
```

### `router-ai/app/api/v1/embed.py` — reemplazar completo

```python
import uuid
from fastapi import APIRouter, HTTPException, Request, status
from app.models.request import EmbedRequest
from app.models.response import ApiResponse, Meta, EmbedResponse, ErrorResponse
from app.core.registry import registry

router = APIRouter()


@router.post("/embed", response_model=ApiResponse)
async def embed(request: EmbedRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", str(uuid.uuid4()))
    trace_id = getattr(http_request.state, "trace_id", None)

    adapter = registry.get(request.provider)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorResponse(
                code="PROVIDER_NOT_FOUND",
                message=f"Proveedor '{request.provider}' no está registrado.",
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
    try:
        result: EmbedResponse = await adapter.embed(request)
        registry.record_success(request.provider)
        return ApiResponse(data=result.model_dump(), meta=Meta(request_id=request_id))
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                code="CAPABILITY_NOT_SUPPORTED",
                message="Este proveedor no soporta embeddings.",
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
    except Exception as e:
        registry.record_failure(request.provider)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                code="PROVIDER_ERROR",
                message=str(e),
                trace_id=trace_id,
                provider=request.provider,
            ).model_dump(),
        )
```

---

## Fix 7 — M-1: Circuit breaker por proveedor

### 1. Crear `router-ai/app/core/circuit_breaker.py` (archivo nuevo)

```python
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    provider: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _success_count: int = field(default=0, init=False, repr=False)
    _opened_at: Optional[float] = field(default=None, init=False, repr=False)

    def is_available(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._opened_at and (time.monotonic() - self._opened_at) >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit breaker '%s': OPEN → HALF_OPEN", self.provider)
                return True
            return False
        return True  # HALF_OPEN

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker '%s': HALF_OPEN → CLOSED", self.provider)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker '%s': ABIERTO tras %d fallos",
                self.provider, self._failure_count,
            )

    @property
    def state(self) -> str:
        return self._state.value
```

### 2. `router-ai/app/core/registry.py` — reemplazar completo

```python
import logging
from typing import TYPE_CHECKING
from app.core.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from app.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, "BaseAdapter"] = {}
        self._breakers: dict[str, CircuitBreaker] = {}

    def register(self, name: str, adapter: "BaseAdapter") -> None:
        key = name.lower()
        self._adapters[key] = adapter
        self._breakers[key] = CircuitBreaker(provider=key)
        logger.info("Proveedor registrado: %s", name)

    def get(self, name: str) -> "BaseAdapter | None":
        key = name.lower()
        breaker = self._breakers.get(key)
        if breaker and not breaker.is_available():
            logger.warning("Circuit breaker abierto para '%s'", key)
            return None
        return self._adapters.get(key)

    def record_success(self, name: str) -> None:
        breaker = self._breakers.get(name.lower())
        if breaker:
            breaker.record_success()

    def record_failure(self, name: str) -> None:
        breaker = self._breakers.get(name.lower())
        if breaker:
            breaker.record_failure()

    def list_providers(self) -> list[str]:
        return list(self._adapters.keys())

    def get_circuit_state(self, name: str) -> str | None:
        breaker = self._breakers.get(name.lower())
        return breaker.state if breaker else None

    async def startup(self) -> None:
        from app.core.config import settings
        from app.adapters.anthropic import AnthropicAdapter
        from app.adapters.openai import OpenAIAdapter
        from app.adapters.deepseek import DeepSeekAdapter
        from app.adapters.ollama import OllamaAdapter
        from app.adapters.lmstudio import LMStudioAdapter
        from app.adapters.google import GoogleAdapter

        if settings.anthropic_api_key:
            self.register("anthropic", AnthropicAdapter(settings.anthropic_api_key.get_secret_value()))
        if settings.openai_api_key:
            self.register("openai", OpenAIAdapter(settings.openai_api_key.get_secret_value()))
        if settings.deepseek_api_key:
            self.register("deepseek", DeepSeekAdapter(
                api_key=settings.deepseek_api_key.get_secret_value(),
                base_url=settings.deepseek_base_url,
            ))
        if settings.google_api_key:
            self.register("google", GoogleAdapter(settings.google_api_key.get_secret_value()))
        self.register("ollama", OllamaAdapter(base_url=settings.ollama_base_url))
        self.register("lmstudio", LMStudioAdapter(base_url=settings.lmstudio_base_url))

        if not self._adapters:
            logger.warning("No hay proveedores configurados.")


registry = ProviderRegistry()
```

---

## Verificación final

```bash
cd router-ai
ROUTER_AI_API_KEY=test-key python -m pytest tests/ -v --tb=short
```

Todos los tests deben pasar en verde. Si hay fallos en tests de registry o message/embed,
es probable que los tests usen `response["content"]` en lugar de `response["data"]["content"]`
tras Fix 5 — actualizar los asserts correspondientes.
