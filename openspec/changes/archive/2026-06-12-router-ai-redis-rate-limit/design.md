# Design: router-ai-redis-rate-limit

## Context

`RateLimiter` ya recibe el store por inyección (`RateLimitStore` ABC en `app/core/rate_limit_store.py`), tal como anticipó la spec `rate-limiting`. Lo que falta: la implementación Redis, la selección por entorno y tres defectos que salen a la luz al distribuirlo:

1. La interfaz es síncrona (`increment/get_count/oldest_timestamp`), llamada desde un middleware async — contra Redis necesita `await`.
2. `record_tokens` incrementa **de uno en uno** (`for _ in range(tokens)`): miles de roundtrips por request contra un store remoto.
3. `InMemoryRateLimitStore` usa `time.monotonic()`, que no es comparable entre procesos.

No existe Redis en el proyecto todavía: el `docker-compose.yml` raíz solo tiene `postgres`, `dal-migrate` y `dal`. La arquitectura (CLAUDE.md) prevé Redis para backend y worker, pero la tabla §11 **no autoriza a router-ai a llamar a Redis** — este cambio la enmienda con aprobación del arquitecto.

## Goals / Non-Goals

**Goals:**
- Contadores RPM/TPM compartidos y atómicos entre N réplicas del router-ai.
- Conservar la semántica de **ventana deslizante** de la spec `rate-limiting` (no degradar a ventana fija con ráfagas 2× en los bordes).
- `memory` sigue siendo el default para dev y tests; Redis se activa por configuración.
- Comportamiento definido cuando Redis falla (degradación fail-open, observable en logs y health).

**Non-Goals:**
- Redis para cache de prompts o resultados (eso es del backend, §5 CLAUDE.md).
- Rate limiting por usuario o por API key del cliente (hoy es por proveedor; no cambia).
- Alta disponibilidad de Redis (Sentinel/Cluster) — un solo nodo interno basta para esta fase.
- Persistencia de contadores entre reinicios de Redis (ventanas de 60s; irrelevante).

## Decisions

### D1: Interfaz async con `amount`

```python
class RateLimitStore(ABC):
    async def increment(self, key: str, window_seconds: int, amount: int = 1) -> int: ...
    async def get_count(self, key: str, window_seconds: int = WINDOW) -> int: ...
    async def seconds_until_oldest_expires(self, key: str, window_seconds: int) -> int: ...
```

`record_tokens(tokens)` pasa a una sola llamada `increment(key, WINDOW, tokens)`. `oldest_timestamp` (que filtraba `time.monotonic()`, no portable entre procesos) se sustituye por `seconds_until_oldest_expires`, que cada store calcula con su propio reloj — el contrato deja de exponer timestamps crudos. `RateLimiter.check_request/record_*` y el middleware pasan a async (el middleware ya es async; solo añade awaits).

### D2: Ventana deslizante por buckets de 1 segundo (no ventana fija)

La spec `rate-limiting` exige ventana deslizante de 60s. Implementación Redis sin Lua y sin sorted sets:

```
clave por bucket:  rl:{provider}:{rpm|tpm}:{epoch_second}
increment:         INCRBY bucket amount  +  EXPIRE bucket window+1   (pipeline)
get_count:         MGET de los últimos 60 buckets  →  suma
retry_after:       índice del bucket no-vacío más antiguo  →  segundos hasta salir de la ventana
```

- Atómico entre réplicas: `INCRBY` es atómico; la suma de MGET es una lectura consistente a efectos prácticos (el error máximo es el tráfico de ~1s, aceptable para límites de proveedor).
- Resolución de 1s en lugar de timestamps exactos: una solicitud puede contar hasta 1s de más en la ventana. Aceptado — el InMemory actual ya tiene derivas comparables.
- Alternativas descartadas: ventana fija `INCR`+`EXPIRE` (ráfagas 2× en bordes, contradice la spec); sorted sets `ZADD/ZCARD` (los TPM con `amount` exigen un miembro por token o Lua; más complejidad sin ganancia).

`InMemoryRateLimitStore` se adapta a la misma interfaz async (implementación interna igual, con `amount` y `time.time()`).

### D3: Selección por entorno y degradación fail-open

`RATE_LIMIT_STORE=memory|redis` (default `memory`), `REDIS_URL` (ej. `redis://redis:6379/0`). En el lifespan:

- `redis` con `PING` exitoso → `RedisRateLimitStore`.
- `redis` con Redis inaccesible → **arranca degradado a memoria** con `logger.error` y flag visible en `/v1/health` (`rate_limit_store: "memory (degraded)"`). Razón fail-open: el rate limiter protege cuota de proveedor, no es frontera de seguridad; negar todo el servicio LLM porque Redis cayó es peor que arriesgar un exceso de RPM transitorio. Mismo criterio en runtime: una excepción de Redis en `check/record` permite la petición y la loggea (sin reintentos en el hot path).
- El health/liveness no llama a Redis (lección del hallazgo «healthcheck lento»): reporta el tipo de store decidido en arranque.

### D4: Redis como servicio interno del compose raíz

`redis:7-alpine` en la red `vellum-internal`, sin `ports:` hacia el host (regla §9: la infraestructura no expone puertos fuera de la red Docker), con `healthcheck` (`redis-cli ping`). Sin password en dev local (red interna); `REDIS_URL` admite credenciales para staging/prod vía entorno — nunca commiteadas.

### D5: Enmienda a CLAUDE.md §11

La fila de router-ai pasa a «Puede llamar a: LLMs externos, modelos locales, `redis` (solo rate limiting)». La restricción de no cachear prompts en router-ai (§5) se mantiene intacta. Esta enmienda requiere aprobación explícita del arquitecto: se entiende otorgada al aprobar/aplicar este cambio.

### D6: Tests con fakeredis

`fakeredis` (con soporte asyncio) en `requirements-dev.txt` para testear `RedisRateLimitStore` sin demonio real: mismo contrato, sin dependencia de infraestructura en CI. Un test de integración opcional puede correr contra el Redis del compose si `REDIS_URL` está presente. Los tests existentes de rate limiting siguen pasando con el InMemory adaptado.

## Risks / Trade-offs

- [Fail-open: con Redis caído, N réplicas degradadas vuelven a contar localmente (el problema original)] → Transitorio y observable (log error + health degradado); la alternativa fail-closed tumba todo el servicio LLM por una pieza auxiliar.
- [MGET de 60 claves por check añade latencia (~1 roundtrip extra por request)] → Redis en red interna: sub-milisegundo; irrelevante frente a la latencia del LLM.
- [Buckets de 1s permiten un error de conteo de hasta ~1s de tráfico] → Los límites de proveedor no son exactos a ese nivel; aceptado.
- [El middleware lee `body` para extraer `provider` antes del check — sin cambios aquí, pero las claves Redis dependen de input del cliente] → El `provider` se valida contra el registry aguas abajo; las claves usan el provider en minúsculas y el TTL acota cualquier basura a 61s.

## Migration Plan

1. Añadir servicio `redis` al compose raíz (no afecta a nada existente).
2. Desplegar router-ai con `RATE_LIMIT_STORE=memory` (comportamiento idéntico al actual).
3. Activar `RATE_LIMIT_STORE=redis` por entorno. Rollback: volver a `memory` (solo configuración).

## Open Questions

Ninguna. La enmienda a CLAUDE.md §11 (D5) fue aplicada y aprobada por el arquitecto el 2026-06-11.
