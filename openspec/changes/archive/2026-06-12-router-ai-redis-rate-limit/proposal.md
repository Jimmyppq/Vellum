# Proposal: router-ai-redis-rate-limit

## Why

La auditoría del 31 de mayo (`auditorias/AUDITORIA 31-may.md`, 🔴 «El `InMemoryRateLimitStore` no es compatible con escalado horizontal») señala que con N réplicas del router-ai cada instancia cuenta por su cuenta: un límite de 100 RPM por proveedor se convierte en N×100 RPM reales. Los límites de OpenAI/Anthropic aplican a la API key, no a la instancia, así que el sistema puede agotar la cuota del proveedor sin que ningún contador local lo detecte. Es uno de los dos críticos pendientes del router-ai y bloqueante para staging si se escala.

## What Changes

- Nuevo `RedisRateLimitStore` que implementa la interfaz `RateLimitStore` existente con contadores compartidos en Redis (ventana fija con `INCRBY` + `EXPIRE`, atómico entre réplicas).
- **BREAKING (interno)**: la interfaz `RateLimitStore` pasa a ser asíncrona y `increment` acepta `amount` — el actual `record_tokens` incrementa de uno en uno (O(tokens) por request, inviable contra un store remoto). `InMemoryRateLimitStore` se adapta y sigue siendo el default para dev y tests.
- Selección por variables de entorno: `RATE_LIMIT_STORE=memory|redis` (default `memory`) y `REDIS_URL`; con `redis` configurado pero inaccesible en arranque, el servicio arranca degradado a memoria con warning (fail-open documentado), y cada error de Redis en runtime permite la petición y lo loggea.
- Nuevo servicio `redis` en el `docker-compose.yml` raíz (red interna `vellum-internal`, sin puerto expuesto al host), dependencia `redis>=5` en router-ai.
- Actualización de la tabla de dependencias §11 de `CLAUDE.md`: `router-ai` puede llamar a `redis` (hoy no está autorizado — requiere visto bueno del arquitecto, que se da al aprobar este cambio).
- El healthcheck existente reporta el tipo de store activo (sin llamadas bloqueantes a Redis en el path de liveness).

## Capabilities

### New Capabilities

- `router-ai-distributed-rate-limiting`: rate limiting compartido entre réplicas del router-ai — contrato del store distribuido (atomicidad, ventanas, TTL), selección por entorno, semántica de degradación cuando Redis no está disponible, y contadores RPM/TPM por proveedor.

### Modified Capabilities

- `rate-limiting`: la spec existente del rate limiter de router-ai cambia a nivel de requisito — la interfaz del store pasa a asíncrona con `amount`, y la contabilización de tokens deja de ser un incremento por token.

## Impact

- `router-ai/app/core/rate_limit_store.py`: interfaz async con `amount`; `InMemoryRateLimitStore` adaptado; nuevo `RedisRateLimitStore`
- `router-ai/app/core/rate_limiter.py`: métodos `check_request`/`record_*` async; `retry_after` calculado desde la ventana del store
- `router-ai/app/middleware/rate_limit.py`: awaits sobre el limiter
- `router-ai/app/core/config.py`: `RATE_LIMIT_STORE`, `REDIS_URL`
- `router-ai/app/main.py`: construcción del store según entorno en el lifespan
- `router-ai/requirements.txt`: `redis>=5`
- `docker-compose.yml` raíz: servicio `redis` interno
- `CLAUDE.md` §11: fila de router-ai
- `router-ai/tests/`: tests del store Redis (con fakeredis o Redis del compose de test), de la selección por entorno y de la degradación
- `auditorias/AUDITORIA 31-may.md`: cierre del hallazgo
