# Proposal: dal-execution-state-machine

## Why

La auditoría del 31 de mayo (`auditorias/AUDITORIA 31-may.md`) marcó como crítico que `PATCH /v1/executions/{id}/status` acepta cualquier transición de estado: una ejecución `failed` puede volver a `running`, una `completed` puede re-completarse sobrescribiendo `completed_at` y `output_data`. En un sistema de gobernanza bancario el historial de ejecuciones es un registro de auditoría — una transición inválida lo contamina. Es uno de los tres críticos pendientes antes de conectar el backend.

## What Changes

- Se define una máquina de estados explícita para `executions.status`:
  - `queued → running`, `running → completed`, `running → failed`, `queued → cancelled`
  - `completed`, `failed` y `cancelled` son terminales (un reintento es una nueva ejecución, nunca una resurrección)
  - Cualquier otra transición — incluida misma→misma — devuelve HTTP 409 con código `INVALID_STATE_TRANSITION` (estricto, sin no-op idempotente)
- **BREAKING**: se añade el estado `cancelled` al dominio de `status` (alcanzable solo desde `queued`)
- **BREAKING**: `output_data` solo se acepta en transiciones hacia estado terminal; en otro caso el request se rechaza
- Se añade `cost` opcional a `ExecutionStatusUpdate`, aceptado solo en transiciones terminales (cierra también el hallazgo 🟡 "campo `cost` sin poblar")
- La transición se aplica con compare-and-set atómico en el `WHERE` del `UPDATE` (sin race entre lectura y escritura, portable entre los cuatro motores soportados)
- El repositorio deja de señalizar errores con `ValueError` genérico: excepciones tipadas que el router mapea a 404 (`NOT_FOUND`) y 409 (`INVALID_STATE_TRANSITION`)

## Capabilities

### New Capabilities

- `dal-execution-lifecycle`: ciclo de vida de las ejecuciones en el DAL — estados válidos, transiciones permitidas, inmutabilidad de estados terminales, reglas de escritura de `output_data`/`cost`/`completed_at`, y contrato de errores 404/409 del endpoint de status.

### Modified Capabilities

<!-- Ninguna: las specs dal-api/dal-repositories viven aún en el change in-progress dal-postgres-implementation, no en openspec/specs/. -->

## Impact

- `dal/app/repositories/executions.py`: `update_status` con CAS atómico, excepciones tipadas, validación de `output_data`/`cost`
- `dal/app/routers/executions.py`: mapeo de excepciones a 404/409 con el formato de error estándar (§8 de CLAUDE.md)
- `dal/app/schemas/requests.py`: `ExecutionStatusUpdate` añade `cancelled` al `Literal` y campo `cost` opcional
- `dal/tests/`: tests de matriz de transiciones (válidas, inválidas, misma→misma, 404 vs 409, escritura de output/cost/completed_at)
- Clientes futuros (backend, worker): deben tratar 409 en reintentos como condición esperada; sin impacto hoy porque aún no consumen el endpoint
- Sin migración de esquema: `status` es `String(50)`; el dominio se valida en aplicación
