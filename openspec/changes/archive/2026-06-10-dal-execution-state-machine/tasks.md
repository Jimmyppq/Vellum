# Tasks: dal-execution-state-machine

## 1. Excepciones de dominio y schema de request

- [x] 1.1 Crear excepciones tipadas `ExecutionNotFound` e `InvalidStateTransition(current, requested)` para el repositorio de ejecuciones
- [x] 1.2 Actualizar `ExecutionStatusUpdate` en `dal/app/schemas/requests.py`: añadir `"cancelled"` al `Literal` de `status` y campo `cost: Decimal | None = None`

## 2. Máquina de estados en el repositorio

- [x] 2.1 Definir en `dal/app/repositories/executions.py` el mapa `ALLOWED_SOURCES` (running←queued, completed←running, failed←running, cancelled←queued) y `TERMINAL_STATUSES = {completed, failed, cancelled}`; eliminar el check redundante de `VALID_STATUSES`
- [x] 2.2 Validar antes del UPDATE que `output_data`/`cost` solo acompañan transiciones terminales (excepción propia → 400 `INVALID_PAYLOAD_FOR_TRANSITION`)
- [x] 2.3 Reescribir `update_status` con compare-and-set atómico: `WHERE id = :id AND status IN (orígenes permitidos)`; escribir `completed_at` (UTC) en toda transición terminal
- [x] 2.4 Con `rowcount == 0`, desambiguar con SELECT posterior: inexistente → `ExecutionNotFound`; existente → `InvalidStateTransition` con estado actual y solicitado

## 3. Router y contrato de errores

- [x] 3.1 Mapear en `dal/app/routers/executions.py`: `ExecutionNotFound` → 404 `NOT_FOUND`, `InvalidStateTransition` → 409 `INVALID_STATE_TRANSITION`, payload inválido → 400 `INVALID_PAYLOAD_FOR_TRANSITION`, con formato estándar (`code`, `message`, `trace_id`)
- [x] 3.2 Incluir en el mensaje del 409 el estado actual y el solicitado

## 4. Tests

- [x] 4.1 Tests de matriz de transiciones: las 4 válidas responden 200; muestra representativa de inválidas (terminal→cualquiera, misma→misma, cualquiera→queued, running→cancelled) responden 409 sin modificar la fila
- [x] 4.2 Test 404 vs 409: id inexistente → 404; id existente con transición inválida → 409
- [x] 4.3 Tests de payload: `output_data`+`cost` persisten en transición terminal; `output_data` en transición no terminal → 400 y sin cambio de estado; transición terminal sin payload escribe `completed_at` y deja `output_data`/`cost` en NULL
- [x] 4.4 Test de concurrencia (CAS): dos transiciones `queued→running` sobre la misma fila — exactamente una gana, la otra recibe `InvalidStateTransition`
- [x] 4.5 Test de formato de error: el 409 incluye `error.code`, `error.message` con ambos estados y `error.trace_id`

## 5. Documentación

- [x] 5.1 Documentar la máquina de estados y el contrato 400/404/409 en `docs/DAL-developer-guide.md`, incluida la guía para clientes: tras un timeout, verificar con GET en lugar de re-enviar el PATCH
- [x] 5.2 Anotar en `auditorias/AUDITORIA 31-may.md` que el hallazgo crítico "Sin máquina de estados" y el 🟡 "campo cost sin poblar" quedan resueltos por este cambio
