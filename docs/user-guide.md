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

## Configuración

### Variables de entorno (`.env`)

Copia el archivo de ejemplo y edítalo con tus credenciales reales antes de arrancar el servicio:

```bash
cd router-ai
cp .env.example .env
```

El archivo `.env` contiene dos grupos de configuración:

**Clave interna del router** — la que tus clientes deben enviar en el header `X-API-Key`:

```bash
# Genera una clave segura con:
# openssl rand -base64 32
ROUTER_AI_API_KEY=BblTpOyDpOq8rOU+27VwO0/nhr3P34Cz3E0CpPKhRvY=
```

**API keys de proveedores LLM** — solo incluye las de los proveedores que vayas a usar:

```bash
# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI GPT
OPENAI_API_KEY=sk-...

# DeepSeek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1   # ya tiene valor por defecto

# Google AI Studio (Gemini)
GOOGLE_API_KEY=AIza...

# Proveedores locales (sin API key; ajusta la URL si corren en otro host/puerto)
OLLAMA_BASE_URL=http://localhost:11434
LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

> **Activación automática:** el router registra únicamente los proveedores cuya API key está presente en `.env`. Si omites `OPENAI_API_KEY`, OpenAI no estará disponible y las solicitudes a ese proveedor recibirán `PROVIDER_NOT_FOUND`. Ollama y LM Studio siempre se registran porque son locales y no requieren clave.

Consulta en cualquier momento qué proveedores están activos:

```bash
curl http://localhost:8000/v1/providers -H "X-API-Key: tu-clave-secreta"
```

---

### Límites de uso (`config/rate_limits.yaml`)

El archivo `config/rate_limits.yaml` define cuántas solicitudes y tokens se permiten por minuto para cada proveedor. Se monta como volumen Docker, por lo que puedes modificarlo **sin reconstruir la imagen ni reiniciar el contenedor**.

```yaml
providers:
  anthropic:
    requests_per_minute: 60      # máx. 60 solicitudes por ventana de 60 s
    tokens_per_minute: 100000    # máx. 100 000 tokens por ventana de 60 s

  openai:
    requests_per_minute: 100
    tokens_per_minute: 150000

  deepseek:
    requests_per_minute: 50
    tokens_per_minute: 80000

  google:
    requests_per_minute: 60
    tokens_per_minute: 100000

  ollama:
    requests_per_minute: 200
    tokens_per_minute: null      # null = sin límite (recomendado para modelos locales)

  lmstudio:
    requests_per_minute: 200
    tokens_per_minute: null
```

Ajusta los valores según los límites que imponga tu plan en cada proveedor o según la capacidad de tu infraestructura local. Cuando se supera un límite, la respuesta devuelve HTTP `429` con el campo `retry_after_seconds` indicando cuántos segundos esperar antes de reintentar (ver [Códigos de error](#códigos-de-error)).

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
| `google` | Google Gemini via AI Studio (requiere `GOOGLE_API_KEY`) |
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

# Google Gemini
curl -s -X POST http://localhost:8000/v1/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "google",
    "model": "gemini-2.0-flash",
    "messages": [
      {"role": "user", "content": "¿Cuál es la diferencia entre ML y DL?"}
    ]
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
  "data": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "content": "Claro, te llamas Ana.",
    "usage": {
      "input_tokens": 42,
      "output_tokens": 8
    }
  },
  "meta": {
    "request_id": "d4f8d4c4-2853-4df7-a2c2-b96e4cd09e42",
    "version": "0.1.0"
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

> Nota: Anthropic no soporta embeddings y retorna HTTP 501. Google sí soporta embeddings (`text-embedding-004`).

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

# Embedding con Google (text-embedding-004)
curl -s -X POST http://localhost:8000/v1/embed \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave-secreta" \
  -d '{
    "provider": "google",
    "input": "La inteligencia artificial transforma la industria."
  }' | jq '{provider, model, dimensions: (.embeddings[0] | length)}'

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
  "data": {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "embeddings": [[0.012, -0.034, 0.087, ...]],
    "usage": {
      "input_tokens": 8,
      "output_tokens": 0
    }
  },
  "meta": {
    "request_id": "a1b2c3d4-0000-0000-0000-000000000000",
    "version": "0.1.0"
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
| `X-Request-ID` | UUID v4 único por solicitud; usar para correlacionar con los logs del router-ai |
| `X-Trace-Id` | ID de traza propagado de extremo a extremo; si se envía en el request se reenvía en la respuesta; si no se envía, el router genera uno nuevo |
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
