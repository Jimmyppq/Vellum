## ADDED Requirements

### Requirement: Google Gemini provider registration
El sistema SHALL registrar automáticamente el proveedor `"google"` en el `ProviderRegistry` durante el startup cuando la variable de entorno `GOOGLE_API_KEY` esté presente y no vacía.

#### Scenario: API key presente en entorno
- **WHEN** `GOOGLE_API_KEY` está definida en el entorno
- **THEN** el proveedor `"google"` aparece en la lista de proveedores disponibles

#### Scenario: API key ausente en entorno
- **WHEN** `GOOGLE_API_KEY` no está definida
- **THEN** el proveedor `"google"` no se registra y el resto de proveedores funcionan con normalidad

---

### Requirement: Google Gemini message completion
El sistema SHALL enviar solicitudes de chat al endpoint de Google AI Studio y devolver una `MessageResponse` con `provider="google"`, el nombre del modelo usado y el contenido generado.

#### Scenario: Solicitud sin modelo especificado
- **WHEN** se llama a `message()` sin `request.model`
- **THEN** se usa `gemini-2.0-flash` como modelo por defecto

#### Scenario: Solicitud con modelo explícito
- **WHEN** se llama a `message()` con `request.model = "gemini-1.5-pro"`
- **THEN** la petición a Google usa ese modelo exacto

#### Scenario: Mapeo de rol assistant a model
- **WHEN** `request.messages` contiene un mensaje con `role="assistant"`
- **THEN** se envía a la API de Google con `role="model"`

#### Scenario: Uso de tokens reportado
- **WHEN** Google devuelve `usage_metadata`
- **THEN** `MessageResponse.usage.input_tokens` y `output_tokens` reflejan los valores de `prompt_token_count` y `candidates_token_count` respectivamente

---

### Requirement: Google Gemini streaming
El sistema SHALL soportar streaming de respuestas de Google Gemini, emitiendo `StreamChunk` a medida que llegan los tokens, y un chunk final con `done=True` y el uso total.

#### Scenario: Chunks de texto emitidos progresivamente
- **WHEN** se llama a `stream()` y Google devuelve texto en múltiples partes
- **THEN** se emite un `StreamChunk(delta=<texto>, done=False)` por cada fragmento recibido

#### Scenario: Chunk final con metadatos de uso
- **WHEN** el stream de Google se completa
- **THEN** se emite exactamente un `StreamChunk(done=True, usage=<totales>)` al finalizar

---

### Requirement: Google Gemini embeddings
El sistema SHALL generar embeddings usando el modelo `text-embedding-004` de Google AI Studio y devolver un `EmbedResponse` normalizado.

#### Scenario: Embedding de un texto único
- **WHEN** se llama a `embed()` con `request.input = "texto"`
- **THEN** se devuelve `EmbedResponse` con una lista de un vector de embeddings

#### Scenario: Embedding de múltiples textos
- **WHEN** se llama a `embed()` con `request.input = ["texto1", "texto2"]`
- **THEN** se devuelve `EmbedResponse` con una lista de dos vectores, uno por input

#### Scenario: Modelo de embeddings por defecto
- **WHEN** `request.model` no está especificado
- **THEN** se usa `text-embedding-004`

---

### Requirement: Google Gemini health check
El sistema SHALL verificar la disponibilidad del proveedor Google intentando listar modelos con un timeout de 5 segundos.

#### Scenario: API accesible
- **WHEN** Google AI Studio responde correctamente dentro del timeout
- **THEN** `health()` devuelve `{"status": "ok"}`

#### Scenario: Timeout excedido
- **WHEN** Google AI Studio no responde en 5 segundos
- **THEN** `health()` devuelve `{"status": "error", "detail": "timeout"}`

#### Scenario: Error de API (key inválida, etc.)
- **WHEN** Google AI Studio devuelve un error (ej. 401, 403)
- **THEN** `health()` devuelve `{"status": "error", "detail": <mensaje del error>}`
