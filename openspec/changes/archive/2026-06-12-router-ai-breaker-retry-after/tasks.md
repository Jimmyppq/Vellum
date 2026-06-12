# Tasks: router-ai-breaker-retry-after

## 1. Núcleo

- [x] 1.1 Crear `router-ai/app/core/errors.py` con `ProviderNotFound(provider)` y `ProviderUnavailable(provider, retry_after_seconds)`
- [x] 1.2 Añadir `CircuitBreaker.seconds_until_retry()` (solo significativo en estado OPEN; mínimo 1)
- [x] 1.3 Cambiar `registry.get()` para lanzar `ProviderNotFound` / `ProviderUnavailable` en lugar de devolver `None` ambiguo

## 2. API

- [x] 2.1 Añadir `retry_after_seconds: int | None = None` a `ErrorResponse`
- [x] 2.2 Crear helper común `resolve_adapter(provider, trace_id)` que traduce: `ProviderNotFound` → 422 `PROVIDER_NOT_FOUND` (contrato actual intacto); `ProviderUnavailable` → 503 `PROVIDER_UNAVAILABLE` + header `Retry-After` + `retry_after_seconds`
- [x] 2.3 Usar el helper en `/v1/message`, `/v1/stream` y `/v1/embed` (eliminar los tres bloques duplicados)
- [x] 2.4 Añadir campo `circuit` a `ProviderStatus` y poblarlo en `GET /v1/providers` desde `get_circuit_state()`

## 3. Tests

- [x] 3.1 Breaker abierto → 503 con `code=PROVIDER_UNAVAILABLE`, header `Retry-After` ≥ 1 y `retry_after_seconds` coincidente, sin invocar al adapter
- [x] 3.2 Proveedor inexistente → 422 `PROVIDER_NOT_FOUND` (regresión del contrato actual)
- [x] 3.3 Half-open deja pasar la llamada de prueba (no 503); transición OPEN→HALF_OPEN tras `recovery_timeout`
- [x] 3.4 Mismo contrato 503 en los tres endpoints
- [x] 3.5 `/v1/providers` refleja `circuit: open/closed/half_open`

## 4. Documentación y cierre

- [x] 4.1 Añadir fila 503 `PROVIDER_UNAVAILABLE` a la tabla de errores de `docs/user-guide.md` y documentar la taxonomía de reintentos (429/503 → `Retry-After`; 422 → no reintentar; 502 → backoff propio)
- [x] 4.2 Actualizar la sección de circuit breaker de `docs/developer-guide.md` (excepciones tipadas, `seconds_until_retry`, breaker por réplica)
