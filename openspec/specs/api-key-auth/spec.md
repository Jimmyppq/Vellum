## ADDED Requirements

### Requirement: Validación de API key en todas las solicitudes
El sistema SHALL requerir el header `X-API-Key` en todas las solicitudes a cualquier endpoint del microservicio. La validación SHALL ocurrir en un middleware FastAPI antes de que la petición llegue al handler del endpoint.

#### Scenario: Solicitud con API key válida
- **WHEN** el cliente envía una solicitud con el header `X-API-Key` cuyo valor coincide con `ROUTER_AI_API_KEY` configurado en el entorno
- **THEN** el sistema procesa la solicitud normalmente y retorna la respuesta correspondiente

#### Scenario: Solicitud con API key inválida
- **WHEN** el cliente envía una solicitud con el header `X-API-Key` cuyo valor no coincide con la clave configurada
- **THEN** el sistema retorna HTTP 401 con `{"code": "UNAUTHORIZED", "message": "API key inválida"}` sin procesar la solicitud

#### Scenario: Solicitud sin header X-API-Key
- **WHEN** el cliente envía una solicitud sin incluir el header `X-API-Key`
- **THEN** el sistema retorna HTTP 401 con `{"code": "UNAUTHORIZED", "message": "Header X-API-Key requerido"}` sin procesar la solicitud

### Requirement: Exclusión del endpoint de health del requisito de autenticación
El endpoint `GET /v1/health` SHALL ser accesible sin header `X-API-Key` para permitir comprobaciones de disponibilidad desde sistemas de monitoreo (load balancers, Kubernetes probes).

#### Scenario: Health check sin autenticación
- **WHEN** un sistema de monitoreo llama a `GET /v1/health` sin el header `X-API-Key`
- **THEN** el sistema retorna HTTP 200 con el estado de salud sin solicitar autenticación

### Requirement: API key almacenada como secreto
El sistema SHALL leer la API key desde la variable de entorno `ROUTER_AI_API_KEY` usando `pydantic.SecretStr`. La clave MUST nunca aparecer en logs, trazas de error ni respuestas HTTP.

#### Scenario: API key ausente en el entorno
- **WHEN** el servicio arranca sin la variable `ROUTER_AI_API_KEY` definida
- **THEN** el servicio registra un error de configuración en el log y no arranca (fail-fast)

#### Scenario: Intento de log de la API key
- **WHEN** cualquier componente del sistema intenta registrar en log un objeto que contenga la API key
- **THEN** el valor aparece ofuscado como `**********` debido al uso de `SecretStr`
