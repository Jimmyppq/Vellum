# Proposal: dal-prompt-soft-delete

## Why

La auditoría del 31 de mayo (`auditorias/AUDITORIA 31-may.md`, 🟡 «Hard delete en prompts») señala que el borrado físico de prompts rompe la cadena de auditoría cuando hay ejecuciones asociadas. La exploración confirmó además que el riesgo es latente pero real: `PromptsRepository.delete` y `TranscriptsRepository.delete` ejecutan `DELETE` físico (sin endpoint HTTP aún, y romperían las FKs de versiones/ejecuciones si se cablearan), y el `PATCH /v1/prompts/{id}/status` acepta cualquier salto de estado — el mismo defecto que acabamos de corregir en executions.

## What Changes

- **Soft delete de prompts**: nuevo `DELETE /v1/prompts/{id}` que marca `deleted_at` + `is_deleted` en una sola sentencia atómica (`UPDATE ... WHERE NOT EXISTS`), solo si el prompt no tiene ejecuciones; con ejecuciones responde 409 `PROMPT_HAS_EXECUTIONS` (el camino correcto es deprecarlo).
- **Soft delete de transcripts**: `DELETE /v1/transcripts/{id}` con la misma regla — 409 `TRANSCRIPT_HAS_EXECUTIONS` si hay ejecuciones con ese `transcript_id`.
- Sin endpoint de restore: de cara al usuario la eliminación es definitiva (el frontend avisará); el soft delete preserva la fila solo como salvaguarda de auditoría.
- Las lecturas de prompts y transcripts (GET por id, listados, y subrecursos de versiones) excluyen los soft-deleted por defecto; query param `include_deleted` disponible en el DAL — el backend decide quién lo usa.
- **BREAKING**: se eliminan los métodos `repo.delete` físicos de prompts y transcripts (no expuestos por HTTP hoy).
- **Máquina de estados de prompts** en `PATCH /v1/prompts/{id}/status`: transiciones permitidas `draft→approved`, `approved→deprecated`, `deprecated→approved`; cualquier otra — incluida misma→misma — responde 409 `INVALID_STATE_TRANSITION` (mismo patrón CAS y excepciones tipadas que `dal-execution-state-machine`). Un prompt soft-deleted no admite cambios de status (404).
- Migración Alembic reversible: columnas `deleted_at` (timestamp nullable) e `is_deleted` (boolean not null default false) en `prompts` y `transcripts`, con índice parcial o simple según portabilidad.

## Capabilities

### New Capabilities

- `dal-prompt-lifecycle`: ciclo de vida de prompts y transcripts en el DAL — máquina de estados de prompts (`draft`/`approved`/`deprecated`), soft delete condicionado a ausencia de ejecuciones para ambas entidades, visibilidad de filas soft-deleted (`include_deleted`), y contrato de errores 404/409.

### Modified Capabilities

<!-- Ninguna: dal-execution-lifecycle no cambia; las specs dal-api/dal-repositories siguen en el change in-progress dal-postgres-implementation. -->

## Impact

- `dal/app/models/schema.py` + nueva migración Alembic: columnas `deleted_at`/`is_deleted` en `prompts` y `transcripts` (upgrade + downgrade)
- `dal/app/repositories/prompts.py`: máquina de estados en `update_status` (CAS), `soft_delete` atómico, filtro `is_deleted` en lecturas, eliminación de `delete` físico
- `dal/app/repositories/transcripts.py`: `soft_delete` atómico, filtro `is_deleted`, eliminación de `delete` físico
- `dal/app/repositories/errors.py`: excepción para "entidad con ejecuciones" (reutiliza `InvalidStateTransition` y `*NotFound` existentes o añade equivalentes para prompts/transcripts)
- `dal/app/routers/prompts.py` y `transcripts.py`: endpoints DELETE, query param `include_deleted`, mapeo de errores al envelope estándar
- `dal/tests/`: tests de soft delete (con/sin ejecuciones, visibilidad, atomicidad) y matriz de transiciones de prompts
- `docs/DAL-developer-guide.md` y `auditorias/AUDITORIA 31-may.md`: documentación y cierre del hallazgo
- Clientes futuros (backend): el DELETE puede devolver 409; la deprecación es el camino para prompts en uso
