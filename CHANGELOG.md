# Changelog

Todos los cambios notables del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y el proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [1.1.0] — 2026-05-29

### Añadido

- **Adaptador Google AI (Gemini)** — nuevo proveedor `"google"` via Google AI Studio:
  - Soporte completo de `message`, `stream` y `embed`
  - Integración con SDK oficial `google-genai >= 1.0`
  - Modelo default para chat: `gemini-2.0-flash`
  - Modelo default para embeddings: `text-embedding-004`
  - Mapeo automático de rol `assistant` → `model` (convención de la API de Google)
  - Health check con timeout de 5 segundos
- **Variable de entorno** `GOOGLE_API_KEY` — registro automático del proveedor cuando está presente; sin efecto cuando está ausente
- **Dependencia** `google-genai >= 1.0` en `requirements.txt`
- **Rate limit** para `google` en `config/rate_limits.yaml` (60 RPM / 100 000 TPM)
- **13 tests unitarios** para `GoogleAdapter` en `tests/test_google_adapter.py`:
  - `message()`: respuesta correcta, modelo default, modelo explícito, mapeo de rol
  - `stream()`: chunks de texto, chunk final con `done=True` y usage, modelo default
  - `embed()`: input único, input lista, modelo default
  - `health()`: ok, timeout, error de API

### Corregido

- **Bug en `tests/conftest.py`** — el fixture `mock_settings` parcheaba la variable de entorno `ROUTER_AI_API_KEY` pero no afectaba el singleton `Settings` ya instanciado al importar el módulo. El `APIKeyMiddleware` comparaba la clave enviada por el cliente contra el valor original del proceso, resultando en `HTTP 401` en todos los tests que usaban el fixture `client`. Corregido parcheando directamente `config.settings.router_ai_api_key` sobre la instancia. Resuelve 12 tests que fallaban.

### Actualizado

- `docs/developer-guide.md` — diagrama de arquitectura, estructura de proyecto, snippets de registry, tabla de variables de entorno, tabla de rate limits y tabla de dependencias
- `docs/user-guide.md` — sección de configuración `.env`, tabla de proveedores, YAML de rate limits, nota de soporte de embeddings, nuevos ejemplos curl para `google` en `/v1/message` y `/v1/embed`
- `router-ai/.env.example` — añadida entrada `GOOGLE_API_KEY`

---

## [1.0.1] — 2026-05-29

### Añadido

- Specs de capacidades publicadas en `openspec/specs/`:
  - `api-key-auth` — autenticación mediante `X-API-Key`
  - `audit-logging` — logging estructurado y trazabilidad por solicitud
  - `health-monitoring` — endpoints de estado del servicio y proveedores
  - `llm-routing` — enrutamiento de solicitudes al adaptador correspondiente
  - `provider-adapters` — contrato `BaseAdapter` y patrón de extensión
  - `rate-limiting` — control de RPM/TPM por proveedor con ventana deslizante
  - `streaming-support` — respuestas en tiempo real via Server-Sent Events
- Change `router-ai` archivado en `openspec/changes/archive/`

---

## [1.0.0] — 2026-05-29

### Añadido

Versión inicial del microservicio `router-ai`: capa de abstracción sobre múltiples proveedores LLM con API unificada.

**Proveedores LLM**
- `anthropic` — Anthropic Claude via SDK oficial (`anthropic`)
- `openai` — OpenAI GPT via SDK oficial (`openai`)
- `deepseek` — DeepSeek via cliente HTTP (`httpx`), API compatible con OpenAI
- `ollama` — Ollama local, sin API key
- `lmstudio` — LM Studio local, sin API key, API compatible con OpenAI

**API REST**
- `POST /v1/message` — chat completion, respuesta completa
- `POST /v1/stream` — chat completion, respuesta en streaming (Server-Sent Events)
- `POST /v1/embed` — generación de embeddings
- `GET /v1/health` — estado del servicio y de cada proveedor (sin autenticación)
- `GET /v1/providers` — lista de proveedores activos con estado

**Infraestructura**
- Autenticación por `X-API-Key` con `secrets.compare_digest` (protección contra timing attacks)
- Rate limiting por proveedor (RPM + TPM) con ventana deslizante de 60 s configurable via YAML
- Logging estructurado en JSON por solicitud (`request_id`, `duration_ms`, `status_code`)
- `ProviderRegistry` singleton: registro automático al arranque según variables de entorno presentes
- Patrón `BaseAdapter` (ABC) para extensión sin tocar endpoints ni middlewares
- Despliegue Docker con `docker-compose.yml`; volúmenes externos para logs y configuración

**Tests**
- Suite de 21 tests: autenticación, health, logging, mensajes, rate limiting, registry y streaming
- Uso de mocks de adaptadores para aislamiento total sin llamadas a APIs externas

**Documentación**
- `docs/developer-guide.md` — guía técnica: arquitectura, decisiones de diseño, configuración, despliegue
- `docs/user-guide.md` — manual de uso: endpoints, ejemplos curl, integración en Python y JavaScript
- `Alcance/` — documentación de arquitectura y alcance del proyecto completo (13 documentos)

[1.1.0]: https://github.com/Jimmyppq/Vellum/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/Jimmyppq/Vellum/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Jimmyppq/Vellum/releases/tag/v1.0.0
