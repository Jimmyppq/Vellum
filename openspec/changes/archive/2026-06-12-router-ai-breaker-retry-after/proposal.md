# Proposal: router-ai-breaker-retry-after

## Why

Cuando el circuit breaker de un proveedor está abierto, `registry.get()` devuelve `None` — la misma señal que un proveedor inexistente — y los tres endpoints (`/v1/message`, `/v1/stream`, `/v1/embed`) responden 422 `PROVIDER_NOT_FOUND` («no está registrado»). El cliente no puede distinguir «no reintentes jamás» (typo en el provider) de «reintenta en N segundos» (proveedor en cuarentena temporal). Para el futuro worker, esa distinción es la base de su política de reintentos; sin ella, o reintenta lo irrecuperable o abandona lo recuperable.

## What Changes

- `registry.get()` deja de devolver `None` ambiguo: lanza excepciones tipadas `ProviderNotFound` (no registrado) y `ProviderUnavailable` (breaker abierto, lleva `retry_after_seconds`).
- Nuevo método público `CircuitBreaker.seconds_until_retry()` que calcula el tiempo hasta el próximo half-open desde `_opened_at` + `recovery_timeout`.
- Los tres endpoints traducen (vía helper común): `ProviderNotFound` → 422 `PROVIDER_NOT_FOUND` (sin cambio de contrato); `ProviderUnavailable` → **503 `PROVIDER_UNAVAILABLE`** con header `Retry-After: N` y `retry_after_seconds` en el cuerpo (simétrico al 429 de rate limiting).
- `GET /v1/providers` expone el estado del breaker por proveedor (`closed` / `open` / `half_open`) — observabilidad, opcional pero barato aquí.
- Documentación de la taxonomía de reintentos para clientes: 429/503 → reintentar tras `Retry-After`; 422 → no reintentar; 502 → fallo puntual, backoff propio.

## Capabilities

### New Capabilities

(Ninguna.)

### Modified Capabilities

- `llm-routing`: el requirement «Enrutamiento dinámico por proveedor» cambia a nivel de comportamiento — el caso «proveedor registrado pero con breaker abierto» deja de responder 422 y pasa a 503 con `Retry-After`.

## Impact

- `router-ai/app/core/circuit_breaker.py`: método `seconds_until_retry()`
- `router-ai/app/core/registry.py`: excepciones tipadas en lugar de `None` ambiguo
- `router-ai/app/core/errors.py` (nuevo) o módulo equivalente: `ProviderNotFound`, `ProviderUnavailable`
- `router-ai/app/api/v1/{chat,stream,embed}.py`: helper común de resolución de adapter + traducción de errores
- `router-ai/app/api/v1/health.py`: estado del breaker en `/v1/providers`
- `router-ai/tests/`: breaker abierto → 503 + header; inexistente → 422; half-open deja pasar; transición open→half-open tras el timeout
- `docs/user-guide.md` y `docs/developer-guide.md`: fila 503 en la tabla de errores + taxonomía de reintentos
- Clientes futuros (worker): regla de reintentos limpia; ningún cliente actual que romper (el backend aún no existe)
