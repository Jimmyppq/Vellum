## ADDED Requirements

### Requirement: Configuración de rate limits desde archivo YAML
El sistema SHALL leer los límites de tasa desde el archivo `config/rate_limits.yaml`, cuya ruta es configurable vía variable de entorno `RATE_LIMITS_CONFIG` (default: `config/rate_limits.yaml`). El archivo SHALL montarse como volumen externo para permitir cambios sin redespliegue. El sistema recargará la configuración al recibir señal `SIGHUP` o en el próximo arranque.

#### Scenario: Carga exitosa del archivo de configuración
- **WHEN** el servicio arranca y `config/rate_limits.yaml` existe y es YAML válido
- **THEN** el sistema carga los límites por proveedor y los aplica desde la primera solicitud

#### Scenario: Archivo de configuración ausente
- **WHEN** el servicio arranca sin encontrar `config/rate_limits.yaml`
- **THEN** el sistema arranca sin rate limiting (límites ilimitados), registra un warning en el log indicando que no se aplican límites

#### Scenario: Proveedor sin sección en el archivo
- **WHEN** el archivo existe pero no tiene sección para un proveedor concreto
- **THEN** ese proveedor opera sin límites (equivalente a `requests_per_minute: null`)

### Requirement: Límite de solicitudes por minuto (RPM) por proveedor
El sistema SHALL rechazar solicitudes que superen el valor `requests_per_minute` configurado para el proveedor indicado. El conteo usa una ventana deslizante de 60 segundos. Un valor `null` significa sin límite.

#### Scenario: Solicitud dentro del límite
- **WHEN** el número de solicitudes al proveedor en el último minuto es menor que `requests_per_minute`
- **THEN** la solicitud se procesa normalmente

#### Scenario: Solicitud que supera el límite RPM
- **WHEN** el número de solicitudes al proveedor en el último minuto iguala o supera `requests_per_minute`
- **THEN** el sistema retorna HTTP 429 con `{"code": "RATE_LIMIT_EXCEEDED", "limit_type": "requests_per_minute", "provider": "...", "retry_after_seconds": N}` donde `N` es el tiempo hasta que expire la solicitud más antigua de la ventana

### Requirement: Límite de tokens por minuto (TPM) por proveedor
El sistema SHALL rechazar solicitudes cuando la suma estimada de tokens de las solicitudes en el último minuto supere `tokens_per_minute`. La estimación de tokens de entrada se realiza antes de enviar al proveedor; los tokens de salida se acumulan a partir del `usage` de respuestas anteriores. Un valor `null` significa sin límite.

#### Scenario: Solicitud dentro del límite de tokens
- **WHEN** la suma de tokens en el último minuto más los tokens estimados de la nueva solicitud no supera `tokens_per_minute`
- **THEN** la solicitud se procesa normalmente

#### Scenario: Solicitud que supera el límite TPM
- **WHEN** la suma de tokens en el último minuto iguala o supera `tokens_per_minute`
- **THEN** el sistema retorna HTTP 429 con `{"code": "RATE_LIMIT_EXCEEDED", "limit_type": "tokens_per_minute", "provider": "...", "retry_after_seconds": N}`

### Requirement: Interfaz RateLimitStore para migración a base de datos
El sistema SHALL implementar el store de contadores mediante una clase abstracta `RateLimitStore` con métodos asíncronos `increment(key, window_seconds, amount=1)`, `get_count(key, window_seconds)` y `seconds_until_oldest_expires(key, window_seconds)`. Las implementaciones SHALL ser `InMemoryRateLimitStore` (default) y `RedisRateLimitStore`, intercambiables sin modificar el middleware de rate limiting. La interfaz SHALL NOT exponer timestamps crudos del reloj de un proceso (no comparables entre réplicas); el tiempo restante de la ventana lo calcula cada store. La contabilización de tokens SHALL realizarse con un único incremento por solicitud (`amount=tokens`), nunca un incremento por token.

#### Scenario: Sustitución del store sin cambios en middleware
- **WHEN** se crea una clase `RedisRateLimitStore` que implementa `RateLimitStore`
- **THEN** el middleware de rate limiting funciona sin modificaciones al inyectar la nueva implementación

#### Scenario: Incremento con cantidad
- **WHEN** se invoca `increment(key, 60, amount=N)` con N > 1
- **THEN** el contador de la ventana aumenta en N con una sola operación

#### Scenario: Reinicio del servicio con store en memoria
- **WHEN** el contenedor se reinicia usando `InMemoryRateLimitStore`
- **THEN** los contadores se reinician a cero (comportamiento esperado para dev; con `RedisRateLimitStore` los contadores sobreviven al reinicio de la réplica)

### Requirement: Headers informativos de rate limit en respuestas
El sistema SHALL incluir en cada respuesta exitosa los headers `X-RateLimit-Remaining-RPM` y `X-RateLimit-Remaining-TPM` con los valores restantes para el proveedor utilizado en esa solicitud.

#### Scenario: Headers presentes en respuesta exitosa
- **WHEN** una solicitud se completa correctamente
- **THEN** la respuesta incluye `X-RateLimit-Remaining-RPM: N` y `X-RateLimit-Remaining-TPM: M` con los valores actuales restantes para ese proveedor en la ventana actual
