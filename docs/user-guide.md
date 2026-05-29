# router-ai — Manual de Uso

## Arranque rápido

```bash
cd router-ai
cp .env.example .env        # Añadir API keys reales
docker compose up -d
```

El servicio queda disponible en `http://localhost:8000`.  
Documentación interactiva (Swagger): `http://localhost:8000/docs`

---

## Autenticación

Todas las solicitudes (excepto `/v1/health`) requieren el header `X-API-Key` con el valor configurado en `ROUTER_AI_API_KEY`:

```bash
-H "X-API-Key: tu-clave-secreta"
```

---

## Proveedores disponibles

| `provider` | Descripción |
|------------|-------------|
| `anthropic` | Anthropic Claude (requiere `ANTHROPIC_API_KEY`) |
| `openai` | OpenAI GPT (requiere `OPENAI_API_KEY`) |
| `deepseek` | DeepSeek (requiere `DEEPSEEK_API_KEY`) |
| `ollama` | Ollama local (sin API key, requiere Ollama corriendo) |
| `lmstudio` | LM Studio local (sin API key, requiere LM Studio corriendo) |

Consulta los proveedores activos en cualquier momento:

```bash
curl http://localhost:8000/v1/providers \
  -H "X-API-Key: tu-clave-secreta"
```

---

## Índice de endpoints

| Método | Endpoint | Autenticación | Descripción |
|--------|----------|:-------------:|-------------|
| `POST` | [`/v1/message`](#post-v1message--mensaje-de-chat) | Requerida | Envía mensajes y recibe la respuesta completa del LLM |
| `POST` | [`/v1/stream`](#post-v1stream--respuesta-en-streaming-sse) | Requerida | Respuesta en tiempo real como Server-Sent Events (SSE) |
| `POST` | [`/v1/embed`](#post-v1embed--embeddings) | Requerida | Genera vectores de embedding para uno o varios textos |
| `GET` | [`/v1/health`](#get-v1health--estado-del-servicio) | **No requerida** | Estado del servicio y de cada proveedor registrado |
| `GET` | [`/v1/providers`](#get-v1providers--lista-de-proveedores-activos) | Requerida | Lista los proveedores activos con su estado actual |

> Todos los endpoints que requieren autenticación deben incluir el header `X-API-Key`.  
> El único endpoint público es `/v1/health`, pensado para health checks de Kubernetes y load balancers.

---

## Endpoints

### `POST /v1/message` — Mensaje de chat

Envía mensajes y recibe la respuesta completa.

**Cuerpo de la solicitud:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `provider` | string | Sí | Proveedor LLM a usar |
| `messages` | array | Sí | Lista de turnos de conversación (`role` + `content`) |
| `model` | string | No | Modelo específico; si se omite usa el modelo por defecto del proveedor |
| `options` | object | No | Parámetros extra del proveedor (ej. `max_tokens`, `temperature`) |

**Ejemplos:**

```bash
# Anthropic Claude
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "anthropic",
    "messages": [
      {"role": "user", "content": "Explica qué es un microservicio en 2 frases."}
    ]
  }' | jq

# OpenAI con modelo explícito
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "content": "Eres un asistente conciso."},
      {"role": "user", "content": "¿Cuál es la capital de Francia?"}
    ]
  }' | jq

# DeepSeek con temperatura personalizada
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "deepseek",
    "model": "deepseek-chat",
    "messages": [
      {"role": "user", "content": "Escribe un haiku sobre el mar."}
    ],
    "options": {"temperature": 0.9}
  }' | jq

# Ollama (modelo local)
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "ollama",
    "model": "llama3.2",
    "messages": [
      {"role": "user", "content": "Hola, ¿cómo estás?"}
    ]
  }' | jq

# LM Studio (modelo cargado localmente)
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "lmstudio",
    "messages": [
      {"role": "user", "content": "Resume en una frase qué es Python."}
    ]
  }' | jq

# Conversación multi-turno
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "openai",
    "messages": [
      {"role": "user",      "content": "Mi nombre es Ana."},
      {"role": "assistant", "content": "Hola Ana, ¿en qué puedo ayudarte?"},
      {"role": "user",      "content": "¿Recuerdas cómo me llamo?"}
    ]
  }' | jq
```

**Respuesta:**

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "content": "Claro, te llamas Ana.",
  "usage": {
    "input_tokens": 42,
    "output_tokens": 8
  }
}
```

---

### `POST /v1/stream` — Respuesta en streaming (SSE)

Misma estructura que `/v1/message` pero la respuesta se recibe en tiempo real como Server-Sent Events.

**Ejemplos:**

```bash
# Streaming básico con Anthropic
curl -s -N -X POST http://localhost:8000/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "anthropic",
    "messages": [
      {"role": "user", "content": "Cuenta del 1 al 10 lentamente."}
    ]
  }'

# Streaming con OpenAI
curl -s -N -X POST http://localhost:8000/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Escribe un poema corto sobre la luna."}
    ]
  }'

# Streaming con LM Studio
curl -s -N -X POST http://localhost:8000/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "lmstudio",
    "messages": [
      {"role": "user", "content": "Explica la recursividad con un ejemplo."}
    ]
  }'
```

**Formato de la respuesta (SSE):**

Cada evento llega como una línea `data: {...}`. La secuencia es:

```
data: {"delta": "Hola", "done": false, "usage": null}

data: {"delta": " mundo", "done": false, "usage": null}

data: {"delta": ".", "done": false, "usage": null}

data: {"delta": "", "done": true, "usage": {"input_tokens": 10, "output_tokens": 3}}
```

El evento final tiene `"done": true` e incluye el resumen de tokens.

**Procesamiento del stream en shell:**

```bash
# Mostrar sólo el texto, sin los metadatos
curl -s -N -X POST http://localhost:8000/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{"provider":"openai","messages":[{"role":"user","content":"Hola"}]}' \
  | grep "^data:" \
  | while IFS= read -r line; do
      json="${line#data: }"
      echo "$json" | jq -r 'if .done then "\n[FIN]" else .delta end' 2>/dev/null
    done
```

---

### `POST /v1/embed` — Embeddings

Genera vectores de embedding para texto.

> Nota: Anthropic no soporta embeddings y retorna HTTP 501.

**Ejemplos:**

```bash
# Embedding de un texto con OpenAI
curl -s -X POST http://localhost:8000/v1/embed \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "openai",
    "input": "La inteligencia artificial transforma la industria."
  }' | jq '{provider, model, dimensions: (.embeddings[0] | length), usage}'

# Embedding de múltiples textos
curl -s -X POST http://localhost:8000/v1/embed \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "openai",
    "model": "text-embedding-3-small",
    "input": [
      "Primera frase de ejemplo.",
      "Segunda frase de ejemplo.",
      "Tercera frase de ejemplo."
    ]
  }' | jq '{provider, model, count: (.embeddings | length)}'

# Embedding con Ollama
curl -s -X POST http://localhost:8000/v1/embed \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "ollama",
    "model": "nomic-embed-text",
    "input": "Texto para vectorizar."
  }' | jq '{provider, model, dim: (.embeddings[0] | length)}'
```

**Respuesta:**

```json
{
  "provider": "openai",
  "model": "text-embedding-3-small",
  "embeddings": [[0.012, -0.034, 0.087, ...]],
  "usage": {
    "input_tokens": 8,
    "output_tokens": 0
  }
}
```

---

### `GET /v1/health` — Estado del servicio

No requiere autenticación. Útil para health checks de Kubernetes y load balancers.

```bash
# Estado global
curl -s http://localhost:8000/v1/health | jq

# Verificar que el servicio está disponible (en scripts)
if curl -sf http://localhost:8000/v1/health > /dev/null; then
  echo "router-ai disponible"
fi
```

**Respuesta (todos ok):**

```json
{
  "status": "ok",
  "providers": {
    "anthropic": "ok",
    "openai": "ok",
    "ollama": "ok"
  }
}
```

**Respuesta (servicio degradado):**

```json
{
  "status": "degraded",
  "providers": {
    "anthropic": "ok",
    "openai": "error: Connection timeout",
    "ollama": "ok"
  }
}
```

---

### `GET /v1/providers` — Lista de proveedores activos

```bash
curl -s http://localhost:8000/v1/providers \
  -H "X-API-Key: tu-clave-secreta" | jq
```

**Respuesta:**

```json
[
  {"name": "anthropic", "status": "ok", "detail": null},
  {"name": "openai",    "status": "ok", "detail": null},
  {"name": "ollama",    "status": "error", "detail": "Ollama no disponible"}
]
```

---

## Códigos de error

| Código HTTP | `code` | Descripción |
|-------------|--------|-------------|
| 401 | `UNAUTHORIZED` | Header `X-API-Key` ausente o inválido |
| 422 | `PROVIDER_NOT_FOUND` | El `provider` indicado no está registrado |
| 422 | Validación Pydantic | Campo requerido ausente o tipo incorrecto |
| 429 | `RATE_LIMIT_EXCEEDED` | Se superó el límite de RPM o TPM del proveedor |
| 501 | `CAPABILITY_NOT_SUPPORTED` | El proveedor no soporta la operación (ej. Anthropic + embed) |
| 502 | `PROVIDER_ERROR` | El proveedor LLM retornó un error |
| 500 | `INTERNAL_ERROR` | Error interno no controlado |

**Ejemplo de respuesta de error:**

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "limit_type": "requests_per_minute",
  "provider": "openai",
  "retry_after_seconds": 23
}
```

---

## Headers de respuesta

| Header | Descripción |
|--------|-------------|
| `X-Request-ID` | UUID v4 único por solicitud; usar para correlacionar con los logs |
| `X-RateLimit-Remaining-RPM` | Solicitudes restantes en la ventana actual (60s) |
| `X-RateLimit-Remaining-TPM` | Tokens restantes en la ventana actual (60s) |

```bash
# Ver todos los headers de respuesta
curl -si -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{"provider":"openai","messages":[{"role":"user","content":"Hola"}]}' \
  | head -20
```

---

## Ejemplos de integración desde código

### Python (`httpx`)

```python
import httpx

BASE_URL = "http://localhost:8000"
API_KEY  = "tu-clave-secreta"
HEADERS  = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Mensaje simple
async with httpx.AsyncClient() as client:
    response = await client.post(f"{BASE_URL}/v1/message", headers=HEADERS, json={
        "provider": "anthropic",
        "messages": [{"role": "user", "content": "¿Qué es FastAPI?"}],
    })
    data = response.json()
    print(data["content"])

# Streaming
async with httpx.AsyncClient() as client:
    async with client.stream("POST", f"{BASE_URL}/v1/stream", headers=HEADERS, json={
        "provider": "openai",
        "messages": [{"role": "user", "content": "Cuenta del 1 al 5."}],
    }) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                import json
                chunk = json.loads(line[6:])
                if not chunk["done"]:
                    print(chunk["delta"], end="", flush=True)
```

### JavaScript / Node.js (`fetch`)

```javascript
const BASE_URL = "http://localhost:8000";
const API_KEY  = "tu-clave-secreta";

// Mensaje simple
const response = await fetch(`${BASE_URL}/v1/message`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
  body: JSON.stringify({
    provider: "openai",
    messages: [{ role: "user", content: "¿Qué es un LLM?" }],
  }),
});
const data = await response.json();
console.log(data.content);

// Streaming con EventSource (desde navegador)
const resp = await fetch(`${BASE_URL}/v1/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
  body: JSON.stringify({
    provider: "anthropic",
    messages: [{ role: "user", content: "Explica la IA en 3 puntos." }],
  }),
});
const reader = resp.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const lines = decoder.decode(value).split("\n");
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const chunk = JSON.parse(line.slice(6));
      if (!chunk.done) process.stdout.write(chunk.delta);
    }
  }
}
```

---

## Rate limiting

Los límites se configuran en `config/rate_limits.yaml` sin necesidad de redesplegar:

```yaml
providers:
  openai:
    requests_per_minute: 100   # null = sin límite
    tokens_per_minute: 150000
```

Cuando se supera un límite, la respuesta incluye `retry_after_seconds` indicando cuántos segundos esperar:

```bash
# Reintentar respetando el límite
RETRY=$(curl -si ... | grep -i "retry-after" | awk '{print $2}')
sleep $RETRY
```
