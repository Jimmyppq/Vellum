# router-ai-distributed-rate-limiting

### Requirement: Contadores compartidos entre réplicas
El router-ai SHALL contabilizar RPM y TPM por proveedor en un store compartido (`RedisRateLimitStore`) cuando esté configurado, de modo que con N réplicas el límite efectivo siga siendo el configurado (no N veces). Los incrementos SHALL ser atómicos (`INCRBY`) y la ventana deslizante de 60 segundos SHALL implementarse con buckets de 1 segundo con TTL, sin scripts Lua ni features no portables de Redis.

#### Scenario: Dos réplicas comparten el límite
- **WHEN** dos instancias del router-ai usan el mismo Redis y el límite de un proveedor es 100 RPM, y entre ambas se han registrado 100 solicitudes en el último minuto
- **THEN** la solicitud 101 recibe 429 `RATE_LIMIT_EXCEEDED` sin importar a qué instancia llegue

#### Scenario: Contabilización de tokens en una sola operación
- **WHEN** se registran 5000 tokens consumidos para un proveedor
- **THEN** el store recibe un único incremento con `amount=5000` (no 5000 incrementos)

#### Scenario: Expiración de la ventana
- **WHEN** las solicitudes registradas salen de la ventana de 60 segundos
- **THEN** dejan de contar para el límite y las claves expiran solas en Redis (TTL), sin limpieza manual

### Requirement: Selección del store por configuración
El router-ai SHALL seleccionar el store mediante `RATE_LIMIT_STORE` (`memory` | `redis`, default `memory`) y `REDIS_URL`. El store en memoria SHALL seguir siendo el comportamiento por defecto en dev y tests. La sustitución SHALL NOT requerir cambios en el middleware ni en `RateLimiter`.

#### Scenario: Default en memoria
- **WHEN** `RATE_LIMIT_STORE` no está definida
- **THEN** el servicio usa `InMemoryRateLimitStore` con el comportamiento actual

#### Scenario: Redis activado
- **WHEN** `RATE_LIMIT_STORE=redis` y `REDIS_URL` apunta a un Redis accesible
- **THEN** el servicio arranca con `RedisRateLimitStore` y lo refleja en el log de arranque

### Requirement: Degradación fail-open ante fallo de Redis
Si `RATE_LIMIT_STORE=redis` y Redis es inaccesible en el arranque, el router-ai SHALL arrancar degradado a `InMemoryRateLimitStore`, registrando un error en el log y reflejando el estado degradado en el healthcheck. En runtime, un error de Redis durante un check o registro SHALL permitir la solicitud (fail-open) y registrar el error. El endpoint de health SHALL NOT realizar llamadas a Redis en el path de liveness; reporta el tipo de store decidido en el arranque.

#### Scenario: Redis caído en arranque
- **WHEN** el servicio arranca con `RATE_LIMIT_STORE=redis` y el `PING` a Redis falla
- **THEN** arranca con el store en memoria, loggea un error y el health reporta el store como degradado

#### Scenario: Error de Redis en runtime
- **WHEN** una operación del store Redis lanza una excepción durante el check de una solicitud
- **THEN** la solicitud se procesa (no se responde 429 ni 500 por el fallo del store) y el error queda en el log

### Requirement: Redis como infraestructura interna
El servicio Redis SHALL desplegarse en la red Docker interna (`vellum-internal`) sin exponer su puerto fuera de ella, con healthcheck propio. Las credenciales de Redis para staging/prod SHALL ir en `REDIS_URL` vía entorno, nunca commiteadas. El router-ai SHALL usar Redis exclusivamente para rate limiting (el cache de prompts sigue siendo responsabilidad del backend).

#### Scenario: Puerto no expuesto
- **WHEN** se levanta el compose del proyecto
- **THEN** Redis es accesible desde los servicios de la red interna y no desde el host
