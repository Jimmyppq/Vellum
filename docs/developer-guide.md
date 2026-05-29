# router-ai — Guía Técnica

## Visión general

`router-ai` es un microservicio FastAPI que actúa como capa de abstracción sobre múltiples proveedores de LLM. El backend invoca una API unificada (`/v1/message`, `/v1/stream`, `/v1/embed`) sin conocer qué proveedor hay detrás. El microservicio enruta cada solicitud al adaptador correspondiente según el parámetro `provider`.

```
Backend ──► router-ai ──► AnthropicAdapter  ──► Anthropic API
                     ├──► OpenAIAdapter     ──► OpenAI API
                     ├──► DeepSeekAdapter   ──► DeepSeek API
                     ├──► OllamaAdapter     ──► Ollama (local)
                     └──► LMStudioAdapter   ──► LM Studio (local)
```

---

## Estructura del proyecto

```
router-ai/
├── app/
│   ├── main.py                    # Entrypoint FastAPI, lifespan, middlewares
│   ├── api/v1/
│   │   ├── router.py              # Agrupación de rutas bajo prefijo /v1
│   │   ├── chat.py                # POST /v1/message
│   │   ├── stream.py              # POST /v1/stream
│   │   ├── embed.py               # POST /v1/embed
│   │   └── health.py              # GET /v1/health, GET /v1/providers
│   ├── adapters/
│   │   ├── base.py                # BaseAdapter (ABC)
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── deepseek.py
│   │   ├── ollama.py
│   │   └── lmstudio.py
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── registry.py            # ProviderRegistry singleton
│   │   ├── auth.py                # verify_api_key()
│   │   ├── logging.py             # setup_logging(), JsonFormatter
│   │   ├── rate_limit_store.py    # RateLimitStore (ABC) + InMemoryRateLimitStore
│   │   └── rate_limiter.py        # RateLimiter (carga YAML, ventana deslizante)
│   ├── middleware/
│   │   ├── auth.py                # APIKeyMiddleware
│   │   ├── logging.py             # AuditLogMiddleware
│   │   └── rate_limit.py          # RateLimitMiddleware
│   └── models/
│       ├── common.py              # Message, UsageInfo
│       ├── request.py             # MessageRequest, EmbedRequest
│       └── response.py            # MessageResponse, EmbedResponse, StreamChunk, ...
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_health.py
│   ├── test_logging.py
│   ├── test_message.py
│   ├── test_rate_limiting.py
│   ├── test_registry.py
│   └── test_stream.py
├── config/
│   └── rate_limits.yaml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Arquitectura y decisiones de diseño

### Patrón Adaptador

Cada proveedor LLM implementa `BaseAdapter` (clase abstracta):

```python
class BaseAdapter(ABC):
    async def message(self, request: MessageRequest) -> MessageResponse: ...
    async def stream(self, request: MessageRequest) -> AsyncGenerator[StreamChunk, None]: ...
    async def embed(self, request: EmbedRequest) -> EmbedResponse: ...
    async def health(self) -> dict: ...
```

Añadir un nuevo proveedor sólo requiere crear una clase nueva que herede de `BaseAdapter` y registrarla en `registry.startup()`. No es necesario tocar ningún endpoint ni middleware.

### ProviderRegistry

Singleton inicializado durante el `lifespan` de FastAPI. Lee las variables de entorno al arranque e instancia sólo los adaptadores con credenciales presentes:

```python
# app/core/registry.py
async def startup(self) -> None:
    if settings.anthropic_api_key:
        self.register("anthropic", AnthropicAdapter(...))
    if settings.openai_api_key:
        self.register("openai", OpenAIAdapter(...))
    # Ollama y LM Studio no requieren API key, siempre se registran
    self.register("ollama", OllamaAdapter(...))
    self.register("lmstudio", LMStudioAdapter(...))
```

### Enrutamiento por solicitud

El parámetro `provider` viaja en el cuerpo JSON de cada petición. Esto permite que el backend cambie de proveedor en cada llamada sin estado en el servidor:

```python
# app/api/v1/chat.py
adapter = registry.get(request.provider)
if adapter is None:
    raise HTTPException(422, ErrorResponse(code="PROVIDER_NOT_FOUND", ...))
return await adapter.message(request)
```

### Streaming con Server-Sent Events

El endpoint `/v1/stream` usa `StreamingResponse` de FastAPI con un generador async que itera sobre el método `stream()` del adaptador y formatea cada chunk como SSE:

```python
async def event_generator():
    async for chunk in adapter.stream(request):
        yield f"data: {chunk.model_dump_json()}\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)
```

Los headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` y `Connection: keep-alive` garantizan compatibilidad con proxies nginx/traefik.

### Middleware stack

Los middlewares se registran en `app/main.py` en orden inverso a su ejecución (Starlette los apila):

```
Solicitud entrante
    │
    ▼
APIKeyMiddleware      ← valida X-API-Key (excepto /v1/health)
    │
    ▼
RateLimitMiddleware  ← verifica RPM/TPM por proveedor
    │
    ▼
AuditLogMiddleware   ← genera request_id, mide duration_ms, loguea
    │
    ▼
Handler del endpoint
```

### Autenticación

`APIKeyMiddleware` compara el header `X-API-Key` contra `ROUTER_AI_API_KEY` usando `secrets.compare_digest` (protección contra ataques de timing). El endpoint `/v1/health` está explícitamente excluido para Kubernetes readiness/liveness probes.

### Logging estructurado

`JsonFormatter` serializa cada `LogRecord` a una línea JSON con campos estándar (`timestamp`, `level`, `logger`, `message`) más campos extra inyectados via `extra={}`. El `AuditLogMiddleware` añade por solicitud: `request_id`, `method`, `path`, `status_code`, `duration_ms`.

`setup_logging()` configura:
- **stdout**: siempre activo
- **archivo rotativo**: `{LOG_DIR}/router-ai.log`, 10 MB × 5 rotaciones; si el directorio no es accesible arranca sin él (no es fatal)

### Rate Limiting

`RateLimiter` carga `config/rate_limits.yaml` al arranque y usa `InMemoryRateLimitStore` (ventana deslizante con `collections.deque`). La arquitectura permite migrar a Redis sin cambiar el middleware:

```
RateLimitStore (ABC)
├── InMemoryRateLimitStore   ← implementación actual
└── RedisRateLimitStore      ← futura migración
```

Para migrar: implementar `RedisRateLimitStore(RateLimitStore)` e inyectarlo en `RateLimiter(config_path, store=RedisRateLimitStore(...))` en el `lifespan`.

---

## Configuración de entorno

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `ROUTER_AI_API_KEY` | API key interna para autenticar clientes | **Sí** |
| `ANTHROPIC_API_KEY` | Clave API de Anthropic | No |
| `OPENAI_API_KEY` | Clave API de OpenAI | No |
| `DEEPSEEK_API_KEY` | Clave API de DeepSeek | No |
| `DEEPSEEK_BASE_URL` | URL base de DeepSeek (default: `https://api.deepseek.com/v1`) | No |
| `OLLAMA_BASE_URL` | URL de Ollama (default: `http://localhost:11434`) | No |
| `LMSTUDIO_BASE_URL` | URL de LM Studio (default: `http://localhost:1234/v1`) | No |
| `LOG_LEVEL` | Nivel de log: `DEBUG`, `INFO`, `WARNING` (default: `INFO`) | No |
| `LOG_DIR` | Directorio para logs persistentes (default: `/logs`) | No |
| `RATE_LIMITS_CONFIG` | Ruta al YAML de rate limits (default: `config/rate_limits.yaml`) | No |

---

## Dependencias

| Paquete | Uso |
|---------|-----|
| `fastapi` | Framework HTTP |
| `uvicorn[standard]` | Servidor ASGI |
| `pydantic` / `pydantic-settings` | Modelos y configuración |
| `anthropic` | SDK de Anthropic |
| `openai` | SDK de OpenAI |
| `httpx` | Cliente HTTP async para DeepSeek, Ollama y LM Studio |
| `pyyaml` | Lectura de `rate_limits.yaml` |

---

## Despliegue

### Docker Compose

```bash
cp .env.example .env
# Editar .env con las API keys reales
docker compose up -d
```

Los volúmenes `./logs` y `./config` se montan automáticamente. Los logs se escriben en `./logs/router-ai.log`.

### Dockerfile (multi-stage)

La imagen usa `python:3.12-slim`. La etapa `builder` instala las dependencias en `/build/deps` para que la imagen final no requiera `pip`. El `PYTHONPATH` apunta a `/app/deps`.

---

## Ejecución de tests

```bash
# Instalar dependencias de desarrollo
pip install -e ".[dev]"

# Ejecutar suite completa
ROUTER_AI_API_KEY=test-key python -m pytest tests/ -v

# Con cobertura
ROUTER_AI_API_KEY=test-key python -m pytest tests/ --cov=app --cov-report=term-missing
```

Los tests usan mocks de adaptadores (`MagicMock`) y deshabilitan el rate limiter por defecto (`set_limiter(None)`), garantizando aislamiento total sin llamadas a APIs externas.

---

## Añadir un nuevo proveedor

1. Crear `app/adapters/nuevo_proveedor.py` heredando de `BaseAdapter` e implementando los 4 métodos.
2. Añadir la variable de entorno en `app/core/config.py` (si requiere API key).
3. Registrar el adaptador en `registry.startup()` dentro de `app/core/registry.py`.
4. Añadir una sección en `config/rate_limits.yaml`.
5. Añadir tests en `tests/` con el adaptador mockeado.

No es necesario modificar ningún endpoint, middleware ni modelo.
