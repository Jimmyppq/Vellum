## Contexto

Los backends de aplicaciones necesitan usar distintos LLMs (Anthropic Claude, OpenAI GPT, DeepSeek, Ollama, etc.) según el caso de uso, coste o disponibilidad. Hoy cada integración requiere código específico por proveedor disperso en distintos servicios. El microservicio `router-ai` centraliza toda esa lógica bajo una interfaz HTTP unificada, de modo que el backend no necesita conocer el proveedor ni manejar sus SDKs.

El servicio se despliega como contenedor Docker independiente y es consumido vía HTTP REST por cualquier backend.

## Goals / Non-Goals

**Goals:**
- Exponer una API REST unificada con métodos `connect`, `message`, `stream`, `embed` y `health`.
- Soportar los proveedores Anthropic, OpenAI, DeepSeek y Ollama en el lanzamiento inicial.
- Permitir agregar nuevos proveedores sin modificar la interfaz pública.
- Gestionar API keys y configuración por proveedor vía variables de entorno.
- Soportar respuestas en streaming mediante Server-Sent Events (SSE).

**Non-Goals:**
- Gestión de sesiones o memoria conversacional persistente (responsabilidad del backend).
- Balanceo de carga o failover automático entre proveedores.
- Autenticación de los clientes del microservicio (se asume red interna).
- Fine-tuning ni entrenamiento de modelos.

## Decisiones

### 1. FastAPI como framework HTTP

**Decisión**: Usar FastAPI con Uvicorn.

**Razón**: Soporte nativo de async/await, generación automática de OpenAPI, tipado estricto con Pydantic y excelente soporte para streaming con `StreamingResponse`. Alternativas como Flask o Django añaden complejidad innecesaria para un microservicio sin estado.

### 2. Patrón Adaptador para proveedores

**Decisión**: Cada proveedor implementa una clase adaptadora que hereda de `BaseAdapter` con métodos abstractos `message()`, `stream()`, `embed()` y `health()`.

**Razón**: Desacopla la lógica de enrutamiento del protocolo de cada proveedor. Agregar un nuevo proveedor sólo requiere crear una nueva clase sin tocar el router ni los endpoints. Alternativa descartada: diccionario de funciones — menos mantenible y no aprovecha el tipado.

```
BaseAdapter (ABC)
├── AnthropicAdapter   → SDK anthropic
├── OpenAIAdapter      → SDK openai
├── DeepSeekAdapter    → HTTP httpx (API compatible con OpenAI, remota)
├── OllamaAdapter      → HTTP httpx (API local, formato propio)
└── LMStudioAdapter    → HTTP httpx (API compatible con OpenAI, local)
```

### 3. Selección de proveedor en cada request

**Decisión**: El parámetro `provider` se pasa en el cuerpo de cada solicitud (no en la sesión ni en headers).

**Razón**: Permite que cada llamada use un proveedor diferente sin estado en el servidor. Simplifica el diseño y la escalabilidad horizontal. El backend tiene control total sobre la selección en cada llamada.

### 4. Registro de adaptadores en tiempo de inicio

**Decisión**: Un `ProviderRegistry` singleton se inicializa al arrancar el servicio, instanciando sólo los adaptadores con credenciales configuradas.

**Razón**: Detecta configuración faltante en el arranque (fail-fast) y evita crear instancias en cada request. Si un proveedor no tiene API key, simplemente no se registra y devuelve error descriptivo.

### 5. Streaming via Server-Sent Events

**Decisión**: Usar `StreamingResponse` de FastAPI con generadores async para SSE.

**Razón**: SSE es más simple que WebSockets para streams unidireccionales y es compatible con cualquier cliente HTTP. Todos los SDK de LLMs soportan iteración de chunks async. Formato: `data: {json}\n\n` con evento final `data: [DONE]\n\n`.

### 6. Modelos Pydantic para request/response

**Decisión**: Definir modelos Pydantic estrictos para todos los contratos de entrada y salida.

**Razón**: Validación automática, documentación OpenAPI generada, y contratos claros entre el backend y el microservicio. Los modelos internos de cada adaptador se mapean al modelo unificado antes de retornar.

## Estructura del Proyecto

```
router-ai/
├── app/
│   ├── main.py               # Entrypoint FastAPI, lifespan
│   ├── api/
│   │   └── v1/
│   │       ├── router.py     # Agrupación de rutas
│   │       ├── chat.py       # POST /v1/message, POST /v1/stream
│   │       ├── embed.py      # POST /v1/embed
│   │       └── health.py     # GET /v1/health
│   ├── adapters/
│   │   ├── base.py           # BaseAdapter (ABC)
│   │   ├── anthropic.py      # AnthropicAdapter
│   │   ├── openai.py         # OpenAIAdapter
│   │   ├── deepseek.py       # DeepSeekAdapter
│   │   └── ollama.py         # OllamaAdapter
│   ├── core/
│   │   ├── registry.py       # ProviderRegistry
│   │   └── config.py         # Settings (pydantic-settings)
│   └── models/
│       ├── request.py        # MessageRequest, EmbedRequest
│       └── response.py       # MessageResponse, EmbedResponse, HealthResponse
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Riesgos / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| Cambios breaking en APIs de proveedores | Versionar los adaptadores; tests de integración por proveedor |
| Latencia adicional por capa de abstracción | Conexiones HTTP keep-alive; adaptadores async nativos; mínimo overhead de mapeo |
| Credenciales expuestas en logs | Nunca loguear headers de autorización; usar pydantic `SecretStr` para API keys |
| Inconsistencia en formatos de error entre proveedores | `ErrorResponse` unificado con `provider`, `code` y `message` |
| Streaming cortado por proxies con timeout bajo | Documentar configuración de timeout; enviar heartbeat SSE cada 15s si necesario |

## Plan de Migración

1. Desplegar `router-ai` como nuevo contenedor (sin afectar servicios existentes).
2. El backend añade el parámetro `provider` en sus llamadas y apunta al nuevo endpoint.
3. Migrar integración por integración (no big-bang); el microservicio coexiste con llamadas directas existentes.
4. Rollback: simplemente redirigir el backend al endpoint anterior; `router-ai` no tiene estado.

## Decisiones Adicionales (preguntas resueltas)

### 7. Autenticación interna con API key

**Decisión**: El microservicio requerirá un header `X-API-Key` en todas las solicitudes. La clave se configura vía variable de entorno `ROUTER_AI_API_KEY`. Se valida en un middleware FastAPI antes de llegar a cualquier endpoint.

**Razón**: Se asume red interna, por lo que mTLS es excesivo. Una API key interna es suficiente para evitar accesos no autorizados sin complejidad de infraestructura. La clave se almacena como `SecretStr` y nunca aparece en logs.

**Alternativa descartada**: mTLS — requiere gestión de certificados, innecesaria en red privada.

### 8. Logging de auditoría en volumen persistente

**Decisión**: Usar el módulo estándar `logging` de Python con `RotatingFileHandler` escribiendo en una ruta configurable vía `LOG_DIR` (default: `/logs`). El nivel se controla con `LOG_LEVEL` (valores: `DEBUG`, `INFO`, `WARNING`). El directorio de logs se monta como volumen Docker externo.

**Razón**: Escribir en el contenedor implica pérdida de logs en reinicios. Un volumen persistente garantiza trazabilidad. El módulo estándar `logging` evita dependencias extra y soporta niveles nativamente. Cada línea de log de auditoría incluirá: timestamp, `request_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `duration_ms` y `status`.

**Formato de log**: JSON estructurado para facilitar ingestión en sistemas de observabilidad (Loki, ELK, etc.).

### 9. Rate limiting por proveedor desde archivo de configuración

**Decisión**: Configurar rate limits en `config/rate_limits.yaml` (montado como volumen). Cada proveedor puede tener límites de `requests_per_minute` y `tokens_per_minute`. El rate limiter usa ventana deslizante en memoria (sin Redis en fase inicial). El archivo incluye una sección `_migration` con instrucciones para migrar a base de datos.

**Razón**: Un archivo YAML externo permite ajustar límites sin redesplegar. La ventana deslizante en memoria es suficiente para una instancia; la migración a Redis/DB se diseña desde el inicio para ser no disruptiva (mismo contrato de interfaz, distinta implementación del store).

**Estructura del archivo**:
```yaml
providers:
  anthropic:
    requests_per_minute: 60
    tokens_per_minute: 100000
  openai:
    requests_per_minute: 100
    tokens_per_minute: 150000
  deepseek:
    requests_per_minute: 50
    tokens_per_minute: 80000
  ollama:
    requests_per_minute: 200
    tokens_per_minute: null  # sin límite
```

**Path de migración a BD**: El store de contadores implementa la interfaz `RateLimitStore` (ABC con métodos `increment()`, `get_count()`). Migrar a Redis implica sólo crear `RedisRateLimitStore` sin cambiar el middleware.
