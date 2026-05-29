## ADDED Requirements

### Requirement: Endpoint de streaming SSE
El sistema SHALL exponer `POST /v1/stream` que acepta el mismo `MessageRequest` que `/v1/message` y retorna una respuesta `text/event-stream` con chunks de texto en formato Server-Sent Events (SSE).

#### Scenario: Stream exitoso
- **WHEN** el backend envía una solicitud válida a `/v1/stream`
- **THEN** el sistema retorna `Content-Type: text/event-stream` y emite eventos con formato `data: {"delta": "...", "provider": "...", "done": false}\n\n` por cada chunk, seguido de un evento final `data: {"done": true, "usage": {...}}\n\n`

#### Scenario: Evento de finalización
- **WHEN** el proveedor LLM indica que el stream ha terminado
- **THEN** el sistema emite exactamente un evento final con `"done": true` y los metadatos de uso (`usage`), y cierra la conexión SSE

#### Scenario: Error durante el stream
- **WHEN** ocurre un error del proveedor en mitad del stream
- **THEN** el sistema emite un evento SSE con `data: {"error": true, "code": "...", "message": "..."}\n\n` y cierra la conexión

### Requirement: Streaming nativo por adaptador
Cada adaptador SHALL implementar el método `stream()` como un generador async (`AsyncGenerator`) que produce objetos `StreamChunk` con los campos `delta` (texto parcial) y `done` (bool).

#### Scenario: Streaming con Anthropic
- **WHEN** se invoca `stream()` en `AnthropicAdapter`
- **THEN** el adaptador usa `client.messages.stream()` del SDK y hace yield de cada `StreamChunk` con el texto del evento `content_block_delta`

#### Scenario: Streaming con OpenAI
- **WHEN** se invoca `stream()` en `OpenAIAdapter`
- **THEN** el adaptador usa `client.chat.completions.create(stream=True)` y hace yield de cada `StreamChunk` con el contenido del delta

#### Scenario: Proveedor sin soporte de streaming
- **WHEN** se invoca `stream()` en un adaptador que no implementa streaming nativo
- **THEN** el adaptador simula el stream realizando la llamada completa y emitiendo un único chunk seguido del evento `done`, sin retornar error

### Requirement: Headers de respuesta SSE correctos
El sistema SHALL incluir en la respuesta de streaming los headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` y `Connection: keep-alive` para garantizar la compatibilidad con proxies y clientes HTTP.

#### Scenario: Headers presentes en respuesta stream
- **WHEN** el cliente hace GET a `/v1/stream` y el servicio inicia la respuesta
- **THEN** la respuesta HTTP contiene los tres headers indicados además de `Content-Type: text/event-stream`
