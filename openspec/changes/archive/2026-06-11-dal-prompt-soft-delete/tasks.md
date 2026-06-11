# Tasks: dal-prompt-soft-delete

## 1. Esquema y migración

- [x] 1.1 Añadir columnas `deleted_at` (DateTime tz, nullable) e `is_deleted` (Boolean, not null, default false) a `prompts` y `transcripts` en `dal/app/models/schema.py`
- [x] 1.2 Crear migración Alembic reversible (add columns con `server_default` false; downgrade con drop), verificando que el test de autogenerate con diff vacío sigue pasando

## 2. Excepciones de dominio

- [x] 2.1 Ampliar `dal/app/repositories/errors.py` con `PromptNotFound`, `TranscriptNotFound`, `PromptHasExecutions` y `TranscriptHasExecutions` (mensaje del 409 de prompts menciona la deprecación como alternativa)

## 3. Repositorio de prompts

- [x] 3.1 Máquina de estados en `update_status`: mapa `PROMPT_ALLOWED_SOURCES` (approved←{draft,deprecated}, deprecated←{approved}), CAS en el `WHERE` (incluyendo `is_deleted == False`), desambiguación 404 vs 409 con `InvalidStateTransition`; eliminar el check de `VALID_STATUSES`
- [x] 3.2 Implementar `soft_delete`: `UPDATE ... WHERE id=:id AND is_deleted=false AND NOT EXISTS(ejecuciones)`; con `rowcount==0` desambiguar `PromptNotFound` (inexistente o ya borrado) vs `PromptHasExecutions`
- [x] 3.3 Eliminar el método `delete` físico; añadir filtro `is_deleted == False` por defecto en `get_by_id` y `list` con parámetro `include_deleted`
- [x] 3.4 Exponer `is_deleted`/`deleted_at` en `PromptResponse`

## 4. Repositorio de transcripts

- [x] 4.1 Implementar `soft_delete` con `NOT EXISTS` sobre `executions.transcript_id` y excepciones `TranscriptNotFound`/`TranscriptHasExecutions`; eliminar `delete` físico
- [x] 4.2 Filtro `is_deleted == False` por defecto en lecturas con parámetro `include_deleted`; exponer `is_deleted`/`deleted_at` en `TranscriptResponse`

## 5. Routers

- [x] 5.1 `DELETE /v1/prompts/{id}`: 200 con la entidad marcada, 404 `NOT_FOUND`, 409 `PROMPT_HAS_EXECUTIONS`; query param `include_deleted` en `GET /v1/prompts` y `GET /v1/prompts/{id}`
- [x] 5.2 Subrecursos de versiones de un prompt soft-deleted responden 404 (verificación del padre en `POST/GET /{id}/versions*`)
- [x] 5.3 `PATCH /v1/prompts/{id}/status`: mapear `InvalidStateTransition` → 409 y `PromptNotFound` → 404 con el envelope estándar
- [x] 5.4 `DELETE /v1/transcripts/{id}` y `include_deleted` en las lecturas de transcripts, con el mismo contrato de errores

## 6. Tests

- [x] 6.1 Soft delete de prompts: sin ejecuciones → 200 con `is_deleted`/`deleted_at` y fila persistente; con ejecuciones → 409 sin modificar; repetido → 404; inexistente → 404
- [x] 6.2 Visibilidad: GET por id y listado excluyen soft-deleted; `include_deleted=true` los muestra; subrecursos de versiones → 404; `PATCH /status` sobre soft-deleted → 404
- [x] 6.3 Matriz de transiciones de prompts: draft→approved, approved→deprecated, deprecated→approved → 200; misma→misma, cualquiera→draft, draft→deprecated → 409 sin modificar
- [x] 6.4 Soft delete de transcripts: misma matriz que 6.1 con `TRANSCRIPT_HAS_EXECUTIONS`
- [x] 6.5 Atomicidad CAS: el soft delete solo se consume una vez (segundo intento → `PromptNotFound`); formato de error 409 con `error.code/message/trace_id`
- [x] 6.6 Migración: upgrade + downgrade ejecutan sin error (o test de autogenerate de diff vacío actualizado)

## 7. Documentación

- [x] 7.1 Documentar en `docs/DAL-developer-guide.md`: soft delete (reglas, `include_deleted`, sin restore), máquina de estados de prompts, e invariantes nuevas
- [x] 7.2 Anotar en `auditorias/AUDITORIA 31-may.md` la resolución del hallazgo 🟡 «Hard delete en prompts» (y que cubre también transcripts y la máquina de estados de prompts)
