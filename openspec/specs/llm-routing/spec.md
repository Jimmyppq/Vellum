## ADDED Requirements

### Requirement: Enrutamiento dinámico por proveedor
El sistema SHALL enrutar cada solicitud al adaptador LLM correspondiente según el valor del campo `provider` incluido en el cuerpo de la petición. El enrutamiento ocurre en tiempo de ejecución sin reiniciar el servicio.

#### Scenario: Enrutamiento exitoso a proveedor registrado
- **WHEN** el backend envía una solicitud con `provider: "anthropic"` y el adaptador Anthropic está registrado
- **THEN** el sistema invoca exclusivamente el adaptador de Anthropic y retorna la respuesta en formato unificado

#### Scenario: Solicitud a proveedor no registrado
- **WHEN** el backend envía `provider: "proveedor-desconocido"` y dicho proveedor no existe en el registro
- **THEN** el sistema retorna HTTP 422 con un `ErrorResponse` que incluye `code: "PROVIDER_NOT_FOUND"` y el nombre del proveedor en el mensaje

#### Scenario: Solicitud sin campo provider
- **WHEN** el backend envía una solicitud sin el campo `provider`
- **THEN** el sistema retorna HTTP 422 con error de validación de Pydantic indicando el campo faltante

### Requirement: Interfaz generalista de mensajería
El sistema SHALL exponer el endpoint `POST /v1/message` que acepta un `MessageRequest` con campos `provider`, `model` (opcional), `messages` (lista de turnos), y `options` (dict opcional), y retorna un `MessageResponse` unificado independientemente del proveedor.

#### Scenario: Mensaje exitoso con modelo explícito
- **WHEN** el backend envía `{"provider": "openai", "model": "gpt-4o", "messages": [{"role": "user", "content": "Hola"}]}`
- **THEN** el sistema retorna `{"provider": "openai", "model": "gpt-4o", "content": "...", "usage": {"input_tokens": N, "output_tokens": M}}`

#### Scenario: Mensaje exitoso con modelo por defecto
- **WHEN** el backend envía una solicitud sin campo `model`
- **THEN** el sistema utiliza el modelo por defecto configurado para ese proveedor en las variables de entorno

#### Scenario: Error del proveedor remoto
- **WHEN** el proveedor LLM retorna un error (ej. límite de rate, clave inválida)
- **THEN** el sistema retorna HTTP 502 con `ErrorResponse` que incluye `provider`, `code` y el mensaje original del error del proveedor

### Requirement: Interfaz generalista de embeddings
El sistema SHALL exponer el endpoint `POST /v1/embed` que acepta un `EmbedRequest` con `provider`, `model` (opcional) y `input` (string o lista de strings), y retorna un `EmbedResponse` con la lista de vectores.

#### Scenario: Embedding de texto único
- **WHEN** el backend envía `{"provider": "openai", "input": "texto de ejemplo"}`
- **THEN** el sistema retorna `{"provider": "openai", "model": "...", "embeddings": [[...]], "usage": {...}}`

#### Scenario: Proveedor sin soporte de embeddings
- **WHEN** el backend solicita embeddings a un proveedor que no implementa este método (ej. Ollama sin modelo de embedding)
- **THEN** el sistema retorna HTTP 501 con `code: "CAPABILITY_NOT_SUPPORTED"` y descripción del motivo
