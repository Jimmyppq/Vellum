## MODIFIED Requirements

### Requirement: Exclusión del endpoint de health del requisito de autenticación
El endpoint `GET /v1/health` SHALL ser accesible sin header `X-API-Key` en todos los entornos para permitir comprobaciones de disponibilidad desde sistemas de monitoreo (load balancers, Kubernetes probes).

#### Scenario: Health check sin autenticación
- **WHEN** un sistema de monitoreo llama a `GET /v1/health` sin el header `X-API-Key`
- **THEN** el sistema retorna HTTP 200 con el estado de salud sin solicitar autenticación, independientemente del valor de `ENV`

## ADDED Requirements

### Requirement: Documentación de la API protegida fuera de desarrollo
Los endpoints de documentación (`/docs`, `/openapi.json`, `/redoc`) SHALL estar exentos de autenticación únicamente cuando el entorno configurado es `dev`. En cualquier otro entorno, el sistema SHALL exigirles el header `X-API-Key` como a cualquier endpoint de negocio.

#### Scenario: Documentación accesible en desarrollo
- **WHEN** `ENV=dev` y un cliente solicita `GET /docs` sin header `X-API-Key`
- **THEN** el sistema retorna la documentación con HTTP 200

#### Scenario: Documentación protegida en producción
- **WHEN** `ENV` es `staging` o `prod` y un cliente solicita `GET /docs`, `GET /openapi.json` o `GET /redoc` sin header `X-API-Key`
- **THEN** el sistema retorna HTTP 401 con `{"code": "UNAUTHORIZED", "message": "Header X-API-Key requerido"}`

#### Scenario: Documentación accesible con API key en producción
- **WHEN** `ENV=prod` y un cliente solicita `GET /docs` con un header `X-API-Key` válido
- **THEN** el sistema retorna la documentación con HTTP 200

### Requirement: Entorno de ejecución configurable y seguro por defecto
El sistema SHALL leer el entorno desde la variable `ENV` (valores válidos: `dev`, `staging`, `prod`, insensible a mayúsculas). Si la variable no está definida o contiene un valor no reconocido, el sistema MUST comportarse como `prod` y registrar un warning en el segundo caso.

#### Scenario: ENV ausente
- **WHEN** el servicio arranca sin la variable `ENV` definida
- **THEN** el entorno efectivo es `prod` y la documentación queda protegida por API key

#### Scenario: ENV con valor no reconocido
- **WHEN** el servicio arranca con `ENV=production` (valor no reconocido)
- **THEN** el sistema registra un warning y el entorno efectivo es `prod`
