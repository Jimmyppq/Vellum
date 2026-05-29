# router-ai — Guía Técnica

## Visión general

`router-ai` es un microservicio FastAPI que actúa como capa de abstracción sobre múltiples proveedores de LLM. El backend invoca una API unificada (`/v1/message`, `/v1/stream`, `/v1/embed`) sin conocer qué proveedor hay detrás. El microservicio enruta cada solicitud al adaptador correspondiente según el parámetro `provider`.

```
Backend ──► router-ai ──► AnthropicAdapter  ──► Anthropic API
                     ├──► OpenAIAdapter     ──► OpenAI API
                     ├──► DeepSeekAdapter   ──► DeepSeek API
                     ├──► GoogleAdapter     ──► Google AI Studio (Gemini)
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
│   │   ├── google.py
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

### Circuit Breaker

`ProviderRegistry` incluye un `CircuitBreaker` por proveedor (en `app/core/circuit_breaker.py`). Cuando un adaptador lanza una excepción, el endpoint llama a `registry.record_failure(provider)`. Tras 5 fallos consecutivos (configurable), el circuito se abre y `registry.get(provider)` devuelve `None` — lo que produce `PROVIDER_NOT_FOUND` hasta que el circuito se recupere.

Estados del circuito:

| Estado | Comportamiento |
|--------|----------------|
| `CLOSED` | Operación normal |
| `OPEN` | Rechaza todas las llamadas; tras 60 s pasa a `HALF_OPEN` |
| `HALF_OPEN` | Permite una llamada de prueba; si hay 2 éxitos consecutivos vuelve a `CLOSED` |

Umbrales por defecto: `failure_threshold=5`, `recovery_timeout=60s`, `success_threshold=2`.

### ProviderRegistry

Singleton inicializado durante el `lifespan` de FastAPI. Lee las variables de entorno al arranque e instancia sólo los adaptadores con credenciales presentes:

```python
# app/core/registry.py
async def startup(self) -> None:
    if settings.anthropic_api_key:
        self.register("anthropic", AnthropicAdapter(...))
    if settings.openai_api_key:
        self.register("openai", OpenAIAdapter(...))
    if settings.deepseek_api_key:
        self.register("deepseek", DeepSeekAdapter(...))
    if settings.google_api_key:
        self.register("google", GoogleAdapter(...))
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
AuditLogMiddleware   ← lee/genera X-Trace-Id, genera request_id, mide duration_ms, loguea
    │
    ▼
Handler del endpoint
```

`AuditLogMiddleware` propaga el header `X-Trace-Id` de extremo a extremo: si el request entrante lo incluye, se reutiliza; si no, se genera uno nuevo. El valor queda disponible en `request.state.trace_id` para los handlers y se devuelve en el header `X-Trace-Id` de la respuesta.

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

### Variables de entorno

`pydantic-settings` carga la configuración en `app/core/config.py` desde tres fuentes en orden de precedencia (mayor a menor): variables de entorno del proceso → archivo `.env` → valores por defecto del modelo. En producción usa variables de entorno; en desarrollo usa `.env`.

```bash
# Punto de partida: copia el ejemplo y edítalo
cp .env.example .env
```

| Variable | Descripción | Requerida | Default |
|----------|-------------|:---------:|---------|
| `ROUTER_AI_API_KEY` | Clave interna; clientes la envían en `X-API-Key` | **Sí** | — |
| `ANTHROPIC_API_KEY` | Clave API de Anthropic | No | `None` |
| `OPENAI_API_KEY` | Clave API de OpenAI | No | `None` |
| `DEEPSEEK_API_KEY` | Clave API de DeepSeek | No | `None` |
| `DEEPSEEK_BASE_URL` | URL base de DeepSeek | No | `https://api.deepseek.com/v1` |
| `GOOGLE_API_KEY` | Clave API de Google AI Studio (Gemini) | No | `None` |
| `OLLAMA_BASE_URL` | URL de Ollama | No | `http://localhost:11434` |
| `LMSTUDIO_BASE_URL` | URL de LM Studio | No | `http://localhost:1234/v1` |
| `LOG_LEVEL` | Nivel de log: `DEBUG` / `INFO` / `WARNING` | No | `INFO` |
| `LOG_DIR` | Directorio para logs persistentes | No | `/logs` |
| `RATE_LIMITS_CONFIG` | Ruta al YAML de rate limits | No | `config/rate_limits.yaml` |
| `MTLS_ENABLED` | Activa TLS mutuo en uvicorn | No | `false` |
| `MTLS_CERT_PATH` | Ruta al certificado del servicio | No | `/certs/service.crt` |
| `MTLS_KEY_PATH` | Ruta a la clave privada del servicio | No | `/certs/service.key` |
| `MTLS_CA_PATH` | Ruta al certificado de la CA interna | No | `/certs/ca.crt` |

Cuando `MTLS_ENABLED=true`, el `entrypoint.sh` arranca uvicorn con `--ssl-keyfile`, `--ssl-certfile` y `--ssl-ca-certs`. En dev local puede dejarse en `false`; en staging/producción debe ser `true`. El volumen `./certs:/certs:ro` en `docker-compose.yml` monta los certificados dentro del contenedor.

**Generación de `ROUTER_AI_API_KEY`:**

```bash
openssl rand -base64 32
```

**Relación entre variables y proveedores activos:**

`ProviderRegistry.startup()` (en `app/core/registry.py`) instancia únicamente los adaptadores cuya variable de API key está definida y no es vacía. Ollama y LM Studio siempre se instancian porque son locales:

```python
if settings.anthropic_api_key:
    self.register("anthropic", AnthropicAdapter(...))
if settings.openai_api_key:
    self.register("openai", OpenAIAdapter(...))
if settings.deepseek_api_key:
    self.register("deepseek", DeepSeekAdapter(...))
if settings.google_api_key:
    self.register("google", GoogleAdapter(...))
self.register("ollama",    OllamaAdapter(...))   # siempre activo
self.register("lmstudio",  LMStudioAdapter(...)) # siempre activo
```

Una variable ausente o comentada en `.env` equivale a deshabilitar el proveedor: las solicitudes a ese proveedor recibirán `HTTP 422 PROVIDER_NOT_FOUND`.

---

### Rate limits (`config/rate_limits.yaml`)

El archivo `config/rate_limits.yaml` controla los límites de uso por proveedor mediante una ventana deslizante de 60 segundos. Se carga al arranque por `RateLimiter` y se monta como volumen Docker independiente de la imagen.

**Estructura:**

```yaml
providers:
  <nombre_proveedor>:
    requests_per_minute: <entero | null>   # null = sin límite
    tokens_per_minute:   <entero | null>
```

**Valores actuales:**

| Proveedor | RPM | TPM |
|-----------|----:|----:|
| `anthropic` | 60 | 100 000 |
| `openai` | 100 | 150 000 |
| `deepseek` | 50 | 80 000 |
| `google` | 60 | 100 000 |
| `ollama` | 200 | sin límite |
| `lmstudio` | 200 | sin límite |

Ajusta los valores según los límites de tu plan en cada proveedor. El cambio es efectivo en el siguiente reinicio del servicio (el YAML se lee en el `lifespan`). Cuando un límite se supera, `RateLimitMiddleware` devuelve `HTTP 429` con el cuerpo:

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "limit_type": "requests_per_minute",
  "provider": "openai",
  "retry_after_seconds": 23
}
```

---

## Dependencias

| Paquete | Uso |
|---------|-----|
| `fastapi` | Framework HTTP |
| `uvicorn[standard]` | Servidor ASGI |
| `pydantic` / `pydantic-settings` | Modelos y configuración |
| `anthropic` | SDK de Anthropic |
| `openai` | SDK de OpenAI |
| `google-genai` | SDK de Google AI Studio (Gemini) |
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
