## ADDED Requirements

### Requirement: Contrato base de adaptadores
El sistema SHALL definir una clase abstracta `BaseAdapter` con los métodos abstractos `message()`, `stream()`, `embed()` y `health()`. Todo adaptador de proveedor MUST heredar de `BaseAdapter` e implementar los cuatro métodos.

#### Scenario: Adaptador incompleto detectado en tiempo de inicio
- **WHEN** se instancia una clase que hereda de `BaseAdapter` sin implementar todos los métodos abstractos
- **THEN** Python lanza `TypeError` en el momento de la instanciación, impidiendo el arranque del servicio

### Requirement: Adaptador Anthropic
El sistema SHALL incluir `AnthropicAdapter` que usa el SDK oficial `anthropic` para invocar la API de Anthropic Claude. SHALL leer la clave desde la variable de entorno `ANTHROPIC_API_KEY`.

#### Scenario: Llamada exitosa a Claude
- **WHEN** se invoca `message()` con mensajes válidos
- **THEN** el adaptador traduce el `MessageRequest` al formato `messages.create` del SDK y mapea la respuesta al `MessageResponse` unificado incluyendo `usage`

#### Scenario: API key no configurada
- **WHEN** `ANTHROPIC_API_KEY` no está definida en el entorno
- **THEN** el adaptador no se registra en el `ProviderRegistry` y las solicitudes a `provider: "anthropic"` retornan HTTP 422 con `code: "PROVIDER_NOT_CONFIGURED"`

### Requirement: Adaptador OpenAI
El sistema SHALL incluir `OpenAIAdapter` que usa el SDK oficial `openai` para invocar la API de OpenAI. SHALL leer la clave desde `OPENAI_API_KEY`.

#### Scenario: Llamada exitosa a GPT
- **WHEN** se invoca `message()` con mensajes válidos
- **THEN** el adaptador usa `client.chat.completions.create()` y mapea la respuesta al formato unificado

#### Scenario: Modelo no soportado
- **WHEN** el backend solicita un modelo que no existe en OpenAI
- **THEN** el adaptador captura el error 404 del SDK y lo envuelve en `ErrorResponse` con `code: "MODEL_NOT_FOUND"`

### Requirement: Adaptador DeepSeek
El sistema SHALL incluir `DeepSeekAdapter` que usa la API REST de DeepSeek (compatible con el protocolo OpenAI) vía `httpx`. SHALL leer la clave desde `DEEPSEEK_API_KEY` y la URL base desde `DEEPSEEK_BASE_URL` (default: `https://api.deepseek.com/v1`).

#### Scenario: Llamada exitosa a DeepSeek
- **WHEN** se invoca `message()` con mensajes válidos
- **THEN** el adaptador realiza un POST al endpoint `/chat/completions` con autenticación Bearer y retorna respuesta en formato unificado

### Requirement: Adaptador Ollama
El sistema SHALL incluir `OllamaAdapter` que usa la API REST local de Ollama vía `httpx`. SHALL leer la URL base desde `OLLAMA_BASE_URL` (default: `http://localhost:11434`). No requiere API key.

#### Scenario: Llamada exitosa a modelo local
- **WHEN** se invoca `message()` y Ollama está corriendo localmente con el modelo solicitado
- **THEN** el adaptador realiza un POST a `/api/chat` y mapea la respuesta al formato unificado

#### Scenario: Ollama no disponible
- **WHEN** Ollama no está corriendo o no es alcanzable
- **THEN** el adaptador captura `httpx.ConnectError` y retorna `ErrorResponse` con `code: "PROVIDER_UNAVAILABLE"`

### Requirement: Registro de adaptadores en tiempo de inicio
El sistema SHALL implementar `ProviderRegistry` que en el evento `startup` de FastAPI instancia todos los adaptadores con credenciales presentes y los indexa por nombre de proveedor (string en minúsculas, ej. `"anthropic"`, `"openai"`).

#### Scenario: Múltiples proveedores configurados
- **WHEN** el servicio arranca con `ANTHROPIC_API_KEY` y `OPENAI_API_KEY` definidas
- **THEN** el registro contiene exactamente los adaptadores `"anthropic"` y `"openai"` listos para usar

#### Scenario: Consulta de proveedores disponibles
- **WHEN** se llama a `registry.list_providers()`
- **THEN** retorna una lista con los nombres de los proveedores actualmente registrados

### Requirement: Adaptador LM Studio
El sistema SHALL incluir `LMStudioAdapter` que usa la API REST local de LM Studio vía `httpx`. LM Studio expone una API compatible con el protocolo OpenAI. SHALL leer la URL base desde `LMSTUDIO_BASE_URL` (default: `http://localhost:1234/v1`). No requiere API key.

#### Scenario: Llamada exitosa a modelo local en LM Studio
- **WHEN** se invoca `message()` y LM Studio está corriendo localmente con un modelo cargado
- **THEN** el adaptador realiza un POST a `/chat/completions` con payload formato OpenAI y mapea la respuesta al `MessageResponse` unificado

#### Scenario: LM Studio no disponible
- **WHEN** LM Studio no está corriendo o no es alcanzable en `LMSTUDIO_BASE_URL`
- **THEN** el adaptador captura `httpx.ConnectError` y retorna `ErrorResponse` con `code: "PROVIDER_UNAVAILABLE"` y detalle descriptivo

#### Scenario: Registro de LMStudio sin API key
- **WHEN** el servicio arranca y `LMSTUDIO_BASE_URL` está definida (o se usa el valor por defecto)
- **THEN** `LMStudioAdapter` se registra en el `ProviderRegistry` bajo la clave `"lmstudio"` sin requerir ninguna API key en el entorno
