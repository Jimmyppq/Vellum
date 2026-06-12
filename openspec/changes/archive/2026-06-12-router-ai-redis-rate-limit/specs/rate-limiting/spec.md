# rate-limiting (delta)

## MODIFIED Requirements

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
