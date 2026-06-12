# Tasks: router-ai-redis-rate-limit

## 1. Interfaz del store y adaptación del existente

- [x] 1.1 Hacer asíncrona la interfaz `RateLimitStore` en `router-ai/app/core/rate_limit_store.py`: `increment(key, window_seconds, amount=1)`, `get_count(key, window_seconds)`, `seconds_until_oldest_expires(key, window_seconds)` (sustituye a `oldest_timestamp`)
- [x] 1.2 Adaptar `InMemoryRateLimitStore` a la nueva interfaz (soporte `amount`, reloj `time.time()`)
- [x] 1.3 Adaptar `RateLimiter` (`check_request`/`record_request`/`record_tokens` async); `record_tokens` pasa a un único `increment` con `amount=tokens`; `retry_after` se calcula con `seconds_until_oldest_expires`
- [x] 1.4 Añadir awaits en `app/middleware/rate_limit.py`

## 2. RedisRateLimitStore

- [x] 2.1 Implementar `RedisRateLimitStore` con buckets de 1 segundo: `INCRBY` + `EXPIRE window+1` en pipeline; `get_count` con `MGET` de los últimos 60 buckets; `seconds_until_oldest_expires` desde el bucket no-vacío más antiguo
- [x] 2.2 Manejo de errores fail-open: cualquier excepción de Redis en `increment`/`get_count` se loggea y no bloquea la solicitud
- [x] 2.3 Añadir `redis>=5` a `router-ai/requirements.txt` y `fakeredis` a `requirements-dev.txt`

## 3. Configuración y arranque

- [x] 3.1 Añadir `RATE_LIMIT_STORE` (`memory`|`redis`, default `memory`) y `REDIS_URL` a `app/core/config.py`
- [x] 3.2 Construcción del store en el lifespan de `app/main.py`: con `redis` hacer `PING`; si falla, degradar a memoria con `logger.error` y marcar estado degradado
- [x] 3.3 Reflejar el tipo de store (y si está degradado) en el endpoint de health sin llamadas a Redis en el path de liveness

## 4. Infraestructura

- [x] 4.1 Añadir servicio `redis` (`redis:7-alpine`) al `docker-compose.yml` raíz: red `vellum-internal`, sin puertos al host, healthcheck `redis-cli ping`
- [x] 4.2 Actualizar la tabla §11 de `CLAUDE.md`: router-ai puede llamar a `redis` — hecho por el arquitecto (2026-06-11), aprobación otorgada

## 5. Tests

- [x] 5.1 Adaptar los tests existentes de rate limiting a la interfaz async (deben seguir cubriendo RPM, TPM, 429, headers)
- [x] 5.2 Tests de `RedisRateLimitStore` con fakeredis: increment con amount, ventana deslizante (expiración de buckets), `seconds_until_oldest_expires`, y dos stores sobre el mismo fakeredis comparten contadores (simula dos réplicas)
- [x] 5.3 Tests de selección por entorno: default memoria; `redis` con PING fallido arranca degradado a memoria
- [x] 5.4 Test de fail-open en runtime: una excepción del store no produce 429 ni 500

## 6. Documentación y cierre

- [x] 6.1 Documentar en la guía del router-ai (o donde corresponda) el store distribuido, las variables de entorno y la semántica de degradación
- [x] 6.2 Anotar en `auditorias/AUDITORIA 31-may.md` la resolución del 🔴 «rate limiter en memoria»
