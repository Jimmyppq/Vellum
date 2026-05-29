## 1. Estructura del Proyecto y Dependencias

- [x] 1.1 Crear la estructura de directorios: `app/api/v1/`, `app/adapters/`, `app/core/`, `app/middleware/`, `app/models/`, `tests/`, `config/`
- [x] 1.2 Crear `pyproject.toml` con dependencias: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `anthropic`, `openai`, `httpx`, `pyyaml`
- [x] 1.3 Crear `.env.example` con todas las variables de entorno documentadas (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `OLLAMA_BASE_URL`, `LMSTUDIO_BASE_URL`, `ROUTER_AI_API_KEY`, `LOG_LEVEL`, `LOG_DIR`, `RATE_LIMITS_CONFIG`)
- [x] 1.4 Crear `Dockerfile` multi-stage con imagen base `python:3.12-slim`; declarar volúmenes `/logs` y `/app/config`
- [x] 1.5 Crear `docker-compose.yml` con el servicio `router-ai`, mapeo de variables de entorno, y montaje de volúmenes para logs (`./logs:/logs`) y configuración (`./config:/app/config`)

## 2. Modelos Pydantic

- [x] 2.1 Crear `app/models/request.py` con `MessageRequest` (campos: `provider`, `model`, `messages`, `options`) y `EmbedRequest` (campos: `provider`, `model`, `input`)
- [x] 2.2 Crear `app/models/response.py` con `MessageResponse`, `EmbedResponse`, `StreamChunk`, `HealthResponse` y `ErrorResponse`
- [x] 2.3 Crear `app/models/common.py` con el modelo `Message` (campos: `role`, `content`) y `UsageInfo` (campos: `input_tokens`, `output_tokens`)

## 3. Configuración Central

- [x] 3.1 Crear `app/core/config.py` con clase `Settings` (pydantic-settings) que lea todas las variables de entorno usando `SecretStr` para las API keys y `ROUTER_AI_API_KEY`; incluir `LOG_LEVEL`, `LOG_DIR` y `RATE_LIMITS_CONFIG`
- [x] 3.2 Crear `app/core/registry.py` con `ProviderRegistry`: método `register()`, `get(provider_name)`, `list_providers()` y `startup()` para inicialización

## 4. Adaptador Base

- [x] 4.1 Crear `app/adapters/base.py` con `BaseAdapter` (ABC) y los métodos abstractos `message()`, `stream()`, `embed()`, `health()`
- [x] 4.2 Añadir tipado explícito en `BaseAdapter`: `message()` retorna `MessageResponse`, `stream()` retorna `AsyncGenerator[StreamChunk, None]`, `embed()` retorna `EmbedResponse`, `health()` retorna `dict`

## 5. Adaptador Anthropic

- [x] 5.1 Crear `app/adapters/anthropic.py` con `AnthropicAdapter` que inicializa `anthropic.AsyncAnthropic` con la API key
- [x] 5.2 Implementar `message()`: traducir `MessageRequest` a `client.messages.create()` y mapear respuesta a `MessageResponse` con `usage`
- [x] 5.3 Implementar `stream()`: usar `client.messages.stream()` y hacer yield de `StreamChunk` por cada evento `content_block_delta`
- [x] 5.4 Implementar `embed()`: retornar `ErrorResponse` con `code: "CAPABILITY_NOT_SUPPORTED"` (Anthropic no soporta embeddings)
- [x] 5.5 Implementar `health()`: llamar a `client.models.list()` con timeout de 5s y retornar estado `ok` o `error`

## 6. Adaptador OpenAI

- [x] 6.1 Crear `app/adapters/openai.py` con `OpenAIAdapter` que inicializa `openai.AsyncOpenAI` con la API key
- [x] 6.2 Implementar `message()`: usar `client.chat.completions.create()` y mapear respuesta a `MessageResponse`
- [x] 6.3 Implementar `stream()`: usar `create(stream=True)` e iterar chunks para hacer yield de `StreamChunk`
- [x] 6.4 Implementar `embed()`: usar `client.embeddings.create()` y mapear a `EmbedResponse`
- [x] 6.5 Implementar `health()`: llamar a `client.models.list()` con timeout de 5s

## 7. Adaptador DeepSeek

- [x] 7.1 Crear `app/adapters/deepseek.py` con `DeepSeekAdapter` usando `httpx.AsyncClient` con `base_url` configurable y header `Authorization: Bearer <key>`
- [x] 7.2 Implementar `message()`: POST a `/chat/completions` con payload formato OpenAI y mapear respuesta a `MessageResponse`
- [x] 7.3 Implementar `stream()`: POST con `stream: true` y parsear chunks SSE del response para hacer yield de `StreamChunk`
- [x] 7.4 Implementar `embed()`: POST a `/embeddings` y mapear a `EmbedResponse`
- [x] 7.5 Implementar `health()`: GET a `/models` con timeout de 5s; capturar `httpx.ConnectError` para retornar `error`

## 8. Adaptador Ollama

- [x] 8.1 Crear `app/adapters/ollama.py` con `OllamaAdapter` usando `httpx.AsyncClient` con `base_url` configurable (sin API key)
- [x] 8.2 Implementar `message()`: POST a `/api/chat` con formato Ollama y mapear respuesta a `MessageResponse`
- [x] 8.3 Implementar `stream()`: POST con `stream: true`, iterar líneas NDJSON y hacer yield de `StreamChunk`
- [x] 8.4 Implementar `embed()`: POST a `/api/embeddings` y mapear a `EmbedResponse`
- [x] 8.5 Implementar `health()`: GET a `/api/tags` con timeout de 5s; capturar `httpx.ConnectError`

## 9. Adaptador LM Studio

- [x] 9.1 Crear `app/adapters/lmstudio.py` con `LMStudioAdapter` usando `httpx.AsyncClient` con `base_url` configurable vía `LMSTUDIO_BASE_URL` (default: `http://localhost:1234/v1`); sin API key requerida
- [x] 9.2 Implementar `message()`: POST a `/chat/completions` con payload formato OpenAI y mapear respuesta a `MessageResponse` (misma lógica de mapeo que `DeepSeekAdapter`)
- [x] 9.3 Implementar `stream()`: POST con `stream: true`, parsear chunks SSE y hacer yield de `StreamChunk`
- [x] 9.4 Implementar `embed()`: POST a `/embeddings` y mapear a `EmbedResponse`
- [x] 9.5 Implementar `health()`: GET a `/models` con timeout de 5s; capturar `httpx.ConnectError` para retornar `{"status": "error", "detail": "LM Studio no disponible"}`

## 10. Endpoints de la API

- [x] 10.1 Crear `app/api/v1/chat.py` con `POST /v1/message`: obtener adaptador del registry, invocar `message()`, manejar errores con `HTTPException`
- [x] 10.2 Crear `app/api/v1/stream.py` con `POST /v1/stream`: retornar `StreamingResponse` con generador async SSE que invoca `stream()` del adaptador y formatea chunks como `data: {json}\n\n`
- [x] 10.3 Añadir headers SSE en `stream.py`: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`
- [x] 10.4 Crear `app/api/v1/embed.py` con `POST /v1/embed`: invocar `embed()` del adaptador y retornar `EmbedResponse`
- [x] 10.5 Crear `app/api/v1/health.py` con `GET /v1/health` (llama `health()` de cada adaptador registrado) y `GET /v1/providers` (lista proveedores del registry)
- [x] 10.6 Crear `app/api/v1/router.py` que agrupa todos los routers con prefijo `/v1`

## 11. Autenticación con API Key

- [x] 11.1 Crear `app/core/auth.py` con la función `verify_api_key(request)` que lee el header `X-API-Key` y compara con `settings.ROUTER_AI_API_KEY` usando comparación segura (`secrets.compare_digest`)
- [x] 11.2 Crear `app/middleware/auth.py` con `APIKeyMiddleware` (Starlette `BaseHTTPMiddleware`) que llama a `verify_api_key` en cada request y retorna 401 si falla, excluyendo la ruta `/v1/health`
- [x] 11.3 Registrar `APIKeyMiddleware` en `app/main.py` antes de los routers

## 12. Logging de Auditoría

- [x] 12.1 Crear `app/core/logging.py` con función `setup_logging()` que configura el logger raíz: handler de stdout y, si `LOG_DIR` es accesible, un `RotatingFileHandler` (maxBytes=10MB, backupCount=5) con formato JSON
- [x] 12.2 Implementar `JsonFormatter` (hereda `logging.Formatter`) que serializa el `LogRecord` a una línea JSON con los campos: `timestamp`, `level`, `logger`, `message` y extras
- [x] 12.3 Crear `app/middleware/logging.py` con `AuditLogMiddleware` que genera un `request_id` UUID v4, mide `duration_ms`, y emite una línea de log al completar cada solicitud con los campos de auditoría
- [x] 12.4 Añadir el header `X-Request-ID` en todas las respuestas con el `request_id` generado por el middleware
- [x] 12.5 Llamar a `setup_logging()` en el evento `lifespan` de `app/main.py` antes de inicializar el registry
- [x] 12.6 Validar que `LOG_LEVEL` sea uno de `DEBUG`, `INFO`, `WARNING` en `Settings`; usar `INFO` como fallback y loguear warning si el valor es inválido

## 13. Rate Limiting

- [x] 13.1 Crear `app/core/rate_limit_store.py` con la clase abstracta `RateLimitStore` (métodos `increment(key, window_seconds) -> int` y `get_count(key) -> int`) y la implementación `InMemoryRateLimitStore` usando `collections.deque` con timestamps por clave
- [x] 13.2 Crear `app/core/rate_limiter.py` con `RateLimiter` que carga `rate_limits.yaml` vía `pyyaml`, expone `check_request(provider, estimated_tokens)` y `record_usage(provider, tokens_used)`, usando `RateLimitStore` internamente
- [x] 13.3 Crear `app/middleware/rate_limit.py` con `RateLimitMiddleware` que invoca `RateLimiter.check_request()` antes de pasar la solicitud al handler; retorna HTTP 429 con `retry_after_seconds` si se supera algún límite
- [x] 13.4 Añadir los headers `X-RateLimit-Remaining-RPM` y `X-RateLimit-Remaining-TPM` en las respuestas exitosas desde `RateLimitMiddleware`
- [x] 13.5 Registrar `RateLimitMiddleware` en `app/main.py` (después de `AuditLogMiddleware`, antes de los routers)
- [x] 13.6 Crear `config/rate_limits.yaml` con valores reales para anthropic, openai, deepseek, ollama y lmstudio; incluir comentarios con el path de migración a `RedisRateLimitStore`

## 14. Entrypoint y Lifecycle

- [x] 14.1 Crear `app/main.py` con la app FastAPI, registrar los tres middlewares en orden (auth → rate_limit → audit_log) y usar `lifespan` para llamar a `setup_logging()` e inicializar el `ProviderRegistry` en startup
- [x] 14.2 Añadir manejo global de errores con `@app.exception_handler` para retornar `ErrorResponse` consistente en excepciones no capturadas

## 15. Tests

- [x] 15.1 Crear `tests/conftest.py` con fixtures de `TestClient` (con API key válida en headers), mocks de adaptadores y `RateLimiter` desactivado por defecto
- [x] 15.2 Escribir tests unitarios para `ProviderRegistry`: registro, lookup por nombre, proveedor no encontrado
- [x] 15.3 Escribir tests de integración para `POST /v1/message` con cada adaptador mockeado (incluido `LMStudioAdapter`)
- [x] 15.4 Escribir tests para `POST /v1/stream` verificando formato SSE y evento final `done`
- [x] 15.5 Escribir tests para `GET /v1/health` con proveedores en estado ok y degraded
- [x] 15.6 Escribir tests para autenticación: solicitud sin `X-API-Key` (401), clave inválida (401), clave válida (200), y que `/v1/health` no requiera autenticación
- [x] 15.7 Escribir tests para rate limiting: solicitud dentro del límite (200 con headers RPM/TPM), solicitud que supera RPM (429), solicitud que supera TPM (429)
- [x] 15.8 Escribir tests para logging: verificar que el log de auditoría incluye `request_id`, `provider`, `duration_ms`; verificar que `X-Request-ID` está en la respuesta
- [x] 15.9 Escribir tests para casos de error: proveedor no registrado, error del proveedor remoto, campo `provider` faltante
