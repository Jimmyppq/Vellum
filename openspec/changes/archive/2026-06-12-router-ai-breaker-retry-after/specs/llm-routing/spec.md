# llm-routing (delta)

## MODIFIED Requirements

### Requirement: Enrutamiento dinámico por proveedor
El sistema SHALL enrutar cada solicitud al adaptador LLM correspondiente según el valor del campo `provider` incluido en el cuerpo de la petición. El enrutamiento ocurre en tiempo de ejecución sin reiniciar el servicio. El sistema SHALL distinguir entre un proveedor no registrado (error permanente, el cliente no debe reintentar) y un proveedor registrado cuyo circuit breaker está abierto (error temporal, el cliente debe reintentar tras el tiempo indicado). La resolución del adaptador y la traducción de estos errores SHALL ser común a los endpoints de mensajería, streaming y embeddings.

#### Scenario: Enrutamiento exitoso a proveedor registrado
- **WHEN** el backend envía una solicitud con `provider: "anthropic"` y el adaptador Anthropic está registrado
- **THEN** el sistema invoca exclusivamente el adaptador de Anthropic y retorna la respuesta en formato unificado

#### Scenario: Solicitud a proveedor no registrado
- **WHEN** el backend envía `provider: "proveedor-desconocido"` y dicho proveedor no existe en el registro
- **THEN** el sistema retorna HTTP 422 con un `ErrorResponse` que incluye `code: "PROVIDER_NOT_FOUND"` y el nombre del proveedor en el mensaje

#### Scenario: Solicitud sin campo provider
- **WHEN** el backend envía una solicitud sin el campo `provider`
- **THEN** el sistema retorna HTTP 422 con error de validación de Pydantic indicando el campo faltante

#### Scenario: Proveedor registrado con circuit breaker abierto
- **WHEN** el backend envía una solicitud a un proveedor registrado cuyo circuit breaker está en estado `open`
- **THEN** el sistema retorna HTTP 503 con `code: "PROVIDER_UNAVAILABLE"`, el header `Retry-After: N` y `retry_after_seconds: N` en el cuerpo, donde N son los segundos hasta el próximo intento half-open, sin invocar al proveedor

#### Scenario: Breaker en half-open deja pasar la llamada de prueba
- **WHEN** el circuit breaker de un proveedor está en `half_open` y llega una solicitud
- **THEN** la solicitud se enruta al adaptador normalmente (no se responde 503)

#### Scenario: Mismo contrato en los tres endpoints
- **WHEN** el circuit breaker de un proveedor está abierto y se invoca `/v1/message`, `/v1/stream` o `/v1/embed`
- **THEN** los tres endpoints responden el mismo 503 `PROVIDER_UNAVAILABLE` con `Retry-After`

## ADDED Requirements

### Requirement: Taxonomía de reintentos para clientes
El contrato de errores del router-ai SHALL permitir a un cliente decidir su política de reintentos sin interpretar mensajes de texto: 429 (`RATE_LIMIT_EXCEEDED`) y 503 (`PROVIDER_UNAVAILABLE`) SHALL incluir `Retry-After` (header) y `retry_after_seconds` (cuerpo) y significan «reintentar tras N segundos»; 422 (`PROVIDER_NOT_FOUND`, validación) significa «no reintentar»; 502 (`PROVIDER_ERROR`) significa «fallo puntual del proveedor, reintento a criterio del cliente con backoff propio».

#### Scenario: Campo retry_after_seconds solo en errores temporales
- **WHEN** se produce un error 422 o 502
- **THEN** el cuerpo no incluye `retry_after_seconds` (o es null), mientras que en 429 y 503 siempre está presente y coincide con el header `Retry-After`

### Requirement: Estado del circuit breaker observable
`GET /v1/providers` SHALL incluir para cada proveedor el estado de su circuit breaker (`closed`, `open` o `half_open`).

#### Scenario: Proveedor en cuarentena visible
- **WHEN** el circuit breaker de un proveedor está abierto y se consulta `/v1/providers`
- **THEN** la entrada de ese proveedor incluye `circuit: "open"`
