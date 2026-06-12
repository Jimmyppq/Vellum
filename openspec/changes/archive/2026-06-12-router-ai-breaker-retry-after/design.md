# Design: router-ai-breaker-retry-after

## Context

`registry.get(name)` ([app/core/registry.py](../../router-ai/app/core/registry.py)) devuelve `None` tanto si el proveedor no está registrado como si su circuit breaker está abierto. Los tres endpoints copian el mismo `if adapter is None: 422 PROVIDER_NOT_FOUND`. El breaker ([app/core/circuit_breaker.py](../../router-ai/app/core/circuit_breaker.py)) ya tiene los datos para calcular el tiempo de espera (`_opened_at`, `recovery_timeout = 60s`), pero no los expone.

Decisión ya tomada con el usuario en exploración: **excepciones tipadas** (no retorno enum/tupla), consistente con el patrón de `errors.py` del DAL.

## Goals / Non-Goals

**Goals:**
- Distinguir estructuralmente «no existe» (422, no reintentar) de «en cuarentena» (503, reintentar tras `Retry-After`).
- Taxonomía de errores coherente para el futuro worker: 429 y 503 comparten la semántica `Retry-After`.
- Eliminar la triplicación del bloque de resolución de adapter en los endpoints.

**Non-Goals:**
- Breaker distribuido en Redis (el estado sigue siendo por réplica; ver Risks).
- Limitar half-open a una sola llamada de prueba concurrente (defecto preexistente, menor, fuera de alcance).
- Cambiar umbrales del breaker (5 fallos / 60s / 2 éxitos) o hacerlos configurables.

## Decisions

### D1: Excepciones tipadas desde el registry

`app/core/errors.py` (nuevo, espejo del patrón del DAL):

- `ProviderNotFound(provider)` — no registrado.
- `ProviderUnavailable(provider, retry_after_seconds)` — breaker abierto.

`registry.get()` lanza en vez de devolver `None`; el caso «disponible» devuelve el adapter como hoy. Alternativa descartada: retorno `tuple[adapter | None, reason]` — obliga a desestructurar en cada llamador y permite ignorar la razón; la excepción hace imposible la ambigüedad.

### D2: `seconds_until_retry()` en el breaker

```python
def seconds_until_retry(self) -> int:
    if self._state is not CircuitState.OPEN or self._opened_at is None:
        return 0
    return max(1, int(self.recovery_timeout - (time.monotonic() - self._opened_at)))
```

`max(1, ...)` y no `max(0, ...)`: si el timeout ya venció, `is_available()` habrá transicionado a half-open antes de llegar aquí; un `Retry-After: 0` sería contradictorio. En HALF_OPEN no se emite 503 (la llamada de prueba pasa), así que el método solo aplica en OPEN.

### D3: Contrato HTTP del 503

```
HTTP/1.1 503 Service Unavailable
Retry-After: 42

{"error_code...} → ErrorResponse:
  code: "PROVIDER_UNAVAILABLE"
  message: "Proveedor 'openai' temporalmente no disponible (circuit breaker abierto); reintentar en 42s"
  provider: "openai"
  trace_id: ...
  retry_after_seconds: 42
```

`retry_after_seconds` se añade a `ErrorResponse` como campo opcional (None en los demás errores) — simétrico al cuerpo del 429 de rate limiting, que ya usa ese nombre. El 422 de `ProviderNotFound` no cambia ni un byte: ningún cliente/test existente se rompe.

### D4: Helper común de resolución

`resolve_adapter(provider, trace_id)` en un módulo compartido del API (p. ej. `app/api/v1/deps.py`): encapsula `registry.get()` + traducción de las dos excepciones a `HTTPException`. Los tres endpoints quedan en una línea y el contrato no puede divergir entre ellos. En `/v1/stream` el chequeo ocurre antes de abrir el SSE, así que el 503 sale como JSON normal.

### D5: Estado del breaker en `/v1/providers`

`ProviderStatus` gana campo `circuit: "closed" | "open" | "half_open"` desde `registry.get_circuit_state()` (ya existe). Solo observabilidad; el healthcheck de liveness no cambia.

## Risks / Trade-offs

- [El breaker es por réplica: el `Retry-After` de una instancia no describe el estado de las demás] → Inocuo para el cliente (el reintento cae donde cae, y como mucho encuentra otra réplica sana); documentado. Un breaker compartido en Redis es deliberadamente non-goal.
- [`registry.get()` pasa de retorno opcional a lanzar excepciones: todo llamador olvidado rompería en runtime] → Solo hay 3 llamadores (los endpoints) + tests; el helper común los unifica. El cambio de firma es la garantía de que nadie vuelva a tratar `None` ambiguo.
- [Clientes que hoy interpreten 422 como «proveedor caído»] → No existen clientes en producción (el backend no está construido); es el momento más barato para corregir el contrato.

## Migration Plan

Despliegue directo del router-ai; sin migraciones ni configuración nueva. Rollback = revertir el código.

## Open Questions

Ninguna — la única decisión de diseño (excepciones tipadas vs retorno estructurado) quedó cerrada en exploración.
