# Design: dal-prompt-soft-delete

## Context

`PromptsRepository.delete` y `TranscriptsRepository.delete` hacen `DELETE` físico. No están expuestos por HTTP, y con datos reales fallarían: las FKs de `prompt_versions.prompt_id`, `executions.prompt_id` y `transcript_versions.transcript_id` no tienen `ON DELETE CASCADE`. `prompts.status` ya tiene ciclo `draft/approved/deprecated`, pero `update_status` acepta cualquier salto. El cambio archivado `dal-execution-state-machine` dejó la infraestructura que este cambio reutiliza: `app/repositories/errors.py` (excepciones tipadas), handler global de `HTTPException` con envelope §8, y el patrón CAS atómico.

Decisiones cerradas con el usuario durante la exploración (no reabrir):
- Sin endpoint de restore; el frontend presentará la eliminación como definitiva.
- `include_deleted` existe en el DAL; el backend decide quién lo usa.
- Transcripts se tratan en este mismo cambio.
- Máquina de estados de prompts incluida aquí; `deprecated → approved` está permitido.

## Goals / Non-Goals

**Goals:**
- Imposibilitar estructuralmente el borrado de prompts/transcripts con ejecuciones, preservando la cadena de auditoría.
- Soft delete atómico y portable (una sentencia, sin race entre "comprobar ejecuciones" y "marcar borrado").
- Máquina de estados explícita para `prompts.status` con el mismo contrato 409 que executions.
- Migración Alembic reversible y portable entre los cuatro motores.

**Non-Goals:**
- Endpoint de restore o papelera visible para usuarios finales.
- Máquina de estados de `transcripts.status` (sus estados los gobierna el pipeline del worker; fuera de alcance).
- Soft delete de versiones, usuarios o conectores.
- Purga física diferida (retention policy) de filas soft-deleted.

## Decisions

### D1: Columnas y migración

`deleted_at: DateTime(timezone=True), nullable` + `is_deleted: Boolean, nullable=False, default=False` en `prompts` y `transcripts`. Dos columnas y no solo `deleted_at` porque el filtro booleano es más legible y portable en índices/queries, y la auditoría pide explícitamente ambas. Migración Alembic con `upgrade` (add columns con `server_default=false` para filas existentes) y `downgrade` (drop). Sin índice nuevo: los listados ya filtran por `status`/`owner_id` indexados y la cardinalidad de `is_deleted=true` será mínima; se añadirá si el volumen lo justifica.

### D2: Soft delete atómico con NOT EXISTS

Una sola sentencia, mismo espíritu CAS que executions — la condición de negocio vive en el `WHERE`:

```python
stmt = (
    update(prompts)
    .where(
        prompts.c.id == id,
        prompts.c.is_deleted == False,
        ~exists(select(executions.c.id).where(executions.c.prompt_id == id)),
    )
    .values(is_deleted=True, deleted_at=now)
)
```

Si `rowcount == 0`, SELECT de desambiguación: no existe o ya está borrado → `PromptNotFound` (404); existe con ejecuciones → `PromptHasExecutions` (409). `NOT EXISTS` correlacionado es SQL estándar, portable. Nota: una ejecución insertada concurrentemente *después* del soft delete no la detiene el DAL (no hay FK que mire `is_deleted`); se acepta — el backend crea ejecuciones solo desde prompts visibles, y la ventana es marginal para el caso de uso (borrar borradores sin uso).

Transcripts: idéntico con `executions.c.transcript_id` y `TranscriptHasExecutions`. Los métodos `delete` físicos se eliminan de ambos repositorios.

### D3: Visibilidad de filas soft-deleted

Todas las lecturas de prompts/transcripts añaden `is_deleted == False` por defecto. `include_deleted: bool = Query(False)` en `GET /v1/prompts`, `GET /v1/prompts/{id}` y equivalentes de transcripts. Los subrecursos de versiones (`POST/GET /{id}/versions...`) tratan al padre soft-deleted como inexistente (404) y **no** exponen `include_deleted`: las versiones de un prompt borrado solo son alcanzables restaurando a mano en BD (escenario de auditoría forense, no de API). `PATCH /{id}/status` sobre un soft-deleted → 404.

Alternativa descartada: vista SQL o filtro automático a nivel de sesión — SQLAlchemy Core no ofrece un hook global fiable para esto; el filtro explícito por repositorio es verboso pero auditable, y el alcance es solo dos entidades.

### D4: Máquina de estados de prompts

```
draft ──▶ approved ◀──▶ deprecated
```

```python
PROMPT_ALLOWED_SOURCES = {
    "approved":   {"draft", "deprecated"},
    "deprecated": {"approved"},
}
```

`draft` no es destino válido (un prompt nunca "des-aprueba" a borrador; para iterar se crea nueva versión). Misma mecánica que executions: CAS en el `WHERE` (`status IN (...) AND is_deleted == False`), desambiguación 404/409, excepción `InvalidStateTransition` reutilizada de `errors.py` con su mapeo 409 ya existente en el patrón del router. No hay estados terminales: `deprecated → approved` es legal por decisión de producto (reactivación).

### D5: Errores tipados

Se amplía `app/repositories/errors.py` con `PromptNotFound`, `TranscriptNotFound`, `PromptHasExecutions`, `TranscriptHasExecutions` (mensaje del 409 indica que la alternativa es `PATCH /status → deprecated` para prompts). `InvalidStateTransition` se reutiliza tal cual. El router mapea al envelope estándar §8 vía el handler global ya existente.

### D6: Contrato del DELETE

`DELETE` exitoso responde **200** con la entidad marcada (consistente con el envelope `{data, meta}` del sistema; un 204 sin cuerpo rompería el formato §8 obligatorio). Repetir el DELETE sobre un ya-borrado responde 404 (coherente con D3: un soft-deleted es invisible).

## Risks / Trade-offs

- [Un filtro `is_deleted` olvidado en una query futura re-expone filas borradas] → El filtro vive centralizado en helpers del repositorio (una función por entidad que construye el SELECT base); los tests de visibilidad cubren cada endpoint de lectura.
- [Ventana de carrera: ejecución creada justo después del soft delete deja una ejecución apuntando a un prompt invisible] → Aceptado y documentado (D2); la FK garantiza integridad referencial en todo caso, y el GET con `include_deleted` permite auditar el prompt.
- [`server_default=false` en la migración bloquea brevemente la tabla en algunos motores al añadir columna NOT NULL] → Tablas aún sin volumen de producción; aceptado.
- [Prohibir `approved → draft` puede sorprender] → Decisión deliberada: iterar es crear versión nueva, no degradar el prompt; si surge la necesidad se amplía el mapa (barato, como `cancelled` en executions).

## Migration Plan

1. Migración Alembic (add columns, reversible) aplicada por el contenedor `dal-migrate` antes de desplegar el código.
2. Despliegue del DAL. Rollback: revertir código + `alembic downgrade -1`.
3. Sin backfill: filas existentes quedan `is_deleted=false`.

## Open Questions

Ninguna — las decisiones de producto se cerraron en exploración (ver Context).
