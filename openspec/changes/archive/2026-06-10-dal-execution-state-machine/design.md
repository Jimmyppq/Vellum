# Design: dal-execution-state-machine

## Context

`ExecutionsRepository.update_status` (dal/app/repositories/executions.py) ejecuta hoy un `UPDATE ... WHERE id = :id` sin consultar el status actual: solo valida que el destino sea uno de los cuatro valores conocidos (check redundante, el `Literal` de Pydantic ya lo garantiza). El router mapea cualquier `ValueError` a 404. `output_data` se acepta en cualquier transición y `cost` no puede poblarse por ningún camino.

Decisiones ya tomadas durante la exploración con el usuario (cerradas, no reabrirlas):
- `failed` es terminal; un reintento es una nueva ejecución.
- Se añade `cancelled` ahora, alcanzable solo desde `queued`.
- Idempotencia estricta: misma→misma es 409, no no-op.
- `output_data` y `cost` solo en transiciones hacia estado terminal.

## Goals / Non-Goals

**Goals:**
- Rechazar estructuralmente toda transición fuera de la máquina de estados, sin race conditions bajo concurrencia.
- Contrato de errores claro: 404 si la ejecución no existe, 409 `INVALID_STATE_TRANSITION` si existe pero la transición no está permitida.
- `output_data`, `cost` y `completed_at` solo escribibles en el paso a estado terminal.
- Portabilidad: la solución funciona igual en PostgreSQL, Oracle, SQL Server y MySQL/MariaDB.

**Non-Goals:**
- Cancelación de ejecuciones `running` (requiere señalización al worker; fuera de alcance).
- Campo `retry_of` o mecánica de reintentos (futuro, en backend/worker).
- CHECK constraint o ENUM en base de datos (el dominio se valida en aplicación; evita migraciones por motor).
- Tabla de historial de transiciones (audit trail de cambios de estado).

## Decisions

### D1: Máquina de estados

```
queued ──▶ running ──▶ completed   (terminal)
   │           └─────▶ failed      (terminal)
   └─────▶ cancelled               (terminal)
```

Representada como mapa destino→orígenes permitidos, que es la forma que necesita el CAS:

```python
ALLOWED_SOURCES = {
    "running":   {"queued"},
    "completed": {"running"},
    "failed":    {"running"},
    "cancelled": {"queued"},
}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
```

`queued` no es destino válido de ningún PATCH (solo se entra por `create`), así que no aparece como clave: pedir `status="queued"` será siempre 409.

### D2: Compare-and-set atómico (vs. SELECT + UPDATE)

El `WHERE` del `UPDATE` incluye el conjunto de orígenes válidos:

```python
update(executions).where(
    executions.c.id == id,
    executions.c.status.in_(ALLOWED_SOURCES[new_status]),
).values(...)
```

Alternativa descartada: leer el status con SELECT, validar en Python y luego UPDATE. Abre una ventana de carrera entre lectura y escritura (dos workers tocando la misma ejecución); evitarla exigiría `SELECT ... FOR UPDATE`, cuya semántica varía entre motores. El CAS es una sola sentencia, atómica y portable.

Si `rowcount == 0`, un SELECT posterior desambigua: fila inexistente → `ExecutionNotFound`; fila existente → `InvalidStateTransition` (incluyendo el status actual en el mensaje). La desambiguación no necesita ser atómica: ya no se va a escribir nada.

Nota: el `.returning(*executions.c)` actual es razonablemente portable en SQLAlchemy 2.x, pero para no depender de él en motores donde flaquea (MySQL), el camino con `rowcount` + SELECT final del estado resultante es aceptable como implementación alternativa; decisión fina en implementación, el contrato no cambia.

### D3: Excepciones tipadas en el repositorio

Se sustituye `ValueError` por excepciones de dominio (p. ej. en `dal/app/repositories/errors.py` o módulo equivalente):

- `ExecutionNotFound` → router responde 404 `NOT_FOUND`
- `InvalidStateTransition` (lleva `current` y `requested`) → router responde 409 `INVALID_STATE_TRANSITION`

El router construye el error con el formato estándar §8 de CLAUDE.md (`code`, `message`, `trace_id`). El mensaje del 409 incluye el estado actual y el solicitado — son metadatos de estado, no datos sensibles.

### D4: Payload condicionado por tipo de transición

`ExecutionStatusUpdate` pasa a:

```python
status: Literal["queued", "running", "completed", "failed", "cancelled"]
output_data: dict[str, Any] | None = None
cost: Decimal | None = None
```

`queued` se mantiene en el `Literal` para que el rechazo sea un 409 coherente (transición inválida) y no un 422 de Pydantic — la máquina de estados es la fuente de verdad, no el schema. La regla "output_data/cost solo en terminales" se valida en el repositorio (o en el router, antes del CAS) y devuelve 400 `INVALID_PAYLOAD_FOR_TRANSITION` si se envían en una transición no terminal. Se valida *antes* de ejecutar el UPDATE para no consumir la transición con un payload inválido.

En transiciones terminales el repositorio escribe `completed_at = now(UTC)` (también para `failed` y `cancelled`: registra cuándo terminó el ciclo de vida, no solo el éxito).

### D5: Sin cambios de esquema

`status` es `String(50)`; `cancelled` cabe sin migración. No se añade CHECK constraint: mantenerlo en aplicación evita divergencia de sintaxis entre los cuatro motores y migraciones acopladas a la máquina de estados. El índice `idx_executions_status` existente sigue sirviendo.

## Risks / Trade-offs

- [El 409 estricto en misma→misma hará que reintentos de red del worker reciban error pese a que la operación original tuvo éxito] → Documentar en la spec que los clientes deben tratar 409 tras un timeout como "verificar estado con GET"; es la semántica elegida deliberadamente para no silenciar dobles procesamientos.
- [Validación de dominio solo en aplicación: un acceso directo a la BD podría insertar estados inválidos] → Aceptado; el DAL es el único componente con drivers de BD por arquitectura (§2.1 CLAUDe.md), y un CHECK por motor costaría más de lo que protege.
- [La desambiguación 404/409 tras `rowcount == 0` lee en una transacción posterior: el estado pudo cambiar entre medias] → Irrelevante para la corrección: cualquier respuesta refleja un estado real reciente y no se escribió nada.
- [Añadir `cancelled` antes de que exista un caso de uso de cancelación] → Coste casi nulo ahora (una arista más en el mapa); añadirlo después tocaría schema Pydantic, máquina y tests ya congelados.

## Migration Plan

Despliegue directo: sin migración Alembic, sin datos existentes que sanear (no hay producción aún). Rollback = revertir el código. Si en el futuro hubiera filas con transiciones contaminadas previas al cambio, quedan como están: el registro histórico no se reescribe.

## Open Questions

Ninguna — las cuatro decisiones de producto se cerraron en exploración (ver Context).
