# dal-prompt-lifecycle

### Requirement: Soft delete de prompts condicionado a ausencia de ejecuciones
El DAL SHALL exponer `DELETE /v1/prompts/{id}` que marca el prompt como eliminado (`is_deleted=true`, `deleted_at` en UTC) sin borrado físico. La operación SHALL aplicarse en una única sentencia atómica cuya cláusula `WHERE` exige que el prompt no esté ya eliminado y no tenga ejecuciones asociadas. Si el prompt tiene ejecuciones, el DAL SHALL responder 409 con código `PROMPT_HAS_EXECUTIONS` y un mensaje que indique la deprecación como alternativa. El DAL SHALL NOT exponer borrado físico de prompts por ningún camino.

#### Scenario: Soft delete de un prompt sin ejecuciones
- **WHEN** se recibe `DELETE /v1/prompts/{id}` sobre un prompt sin ejecuciones asociadas
- **THEN** se responde 200 con el prompt marcado, `is_deleted=true` y `deleted_at` poblado; la fila sigue existiendo en la base de datos

#### Scenario: Prompt con ejecuciones no puede eliminarse
- **WHEN** se recibe `DELETE /v1/prompts/{id}` sobre un prompt con al menos una ejecución
- **THEN** se responde 409 `PROMPT_HAS_EXECUTIONS`, el mensaje menciona la deprecación, y el prompt no se modifica

#### Scenario: DELETE repetido
- **WHEN** se recibe `DELETE /v1/prompts/{id}` sobre un prompt ya soft-deleted
- **THEN** se responde 404 `NOT_FOUND`

#### Scenario: Prompt inexistente
- **WHEN** se recibe `DELETE /v1/prompts/{id}` con un `id` que no existe
- **THEN** se responde 404 `NOT_FOUND`

### Requirement: Soft delete de transcripts condicionado a ausencia de ejecuciones
El DAL SHALL exponer `DELETE /v1/transcripts/{id}` con las mismas reglas que el soft delete de prompts: marca atómica de `is_deleted`/`deleted_at`, rechazo con 409 `TRANSCRIPT_HAS_EXECUTIONS` si existen ejecuciones con ese `transcript_id`, 404 para inexistentes o ya eliminados, y sin borrado físico disponible.

#### Scenario: Soft delete de un transcript sin ejecuciones
- **WHEN** se recibe `DELETE /v1/transcripts/{id}` sobre un transcript que ninguna ejecución referencia
- **THEN** se responde 200 con el transcript marcado `is_deleted=true` y `deleted_at` poblado

#### Scenario: Transcript referenciado por ejecuciones no puede eliminarse
- **WHEN** se recibe `DELETE /v1/transcripts/{id}` y existe al menos una ejecución con ese `transcript_id`
- **THEN** se responde 409 `TRANSCRIPT_HAS_EXECUTIONS` y el transcript no se modifica

### Requirement: Visibilidad de entidades soft-deleted
Las lecturas de prompts y transcripts (`GET` por id y listados) SHALL excluir las filas soft-deleted por defecto. Los endpoints `GET /v1/prompts`, `GET /v1/prompts/{id}` y sus equivalentes de transcripts SHALL aceptar el query param `include_deleted` (boolean, default `false`) que incluye las filas eliminadas; la decisión de quién puede usarlo corresponde al backend. Los subrecursos de un padre soft-deleted (versiones de prompt o de transcript) SHALL tratarse como inexistentes (404) y SHALL NOT aceptar `include_deleted`. Un prompt soft-deleted SHALL NOT admitir cambios de status (404).

#### Scenario: Soft-deleted invisible por defecto
- **WHEN** se solicita `GET /v1/prompts/{id}` o un listado sobre un prompt soft-deleted sin `include_deleted`
- **THEN** el GET por id responde 404 y el listado no incluye el prompt

#### Scenario: include_deleted lo expone
- **WHEN** se solicita `GET /v1/prompts/{id}?include_deleted=true` sobre un prompt soft-deleted
- **THEN** se responde 200 con el prompt, mostrando `is_deleted=true` y `deleted_at`

#### Scenario: Subrecursos de un padre eliminado
- **WHEN** se solicita `GET` o `POST` sobre `/v1/prompts/{id}/versions` con el prompt soft-deleted
- **THEN** se responde 404 `NOT_FOUND`

#### Scenario: Status inmutable tras soft delete
- **WHEN** se recibe `PATCH /v1/prompts/{id}/status` sobre un prompt soft-deleted
- **THEN** se responde 404 `NOT_FOUND`

### Requirement: Máquina de estados de prompts
El DAL SHALL aplicar una máquina de estados explícita sobre `prompts.status` con exclusivamente estas transiciones: `draft → approved`, `approved → deprecated`, `deprecated → approved`. `draft` SHALL NOT ser destino de ninguna transición. Cualquier otra transición — incluida la de un estado a sí mismo — SHALL responder 409 `INVALID_STATE_TRANSITION` con el estado actual y el solicitado en el mensaje, sin modificar el prompt. La transición SHALL aplicarse con compare-and-set atómico portable (estados origen permitidos en el `WHERE` del `UPDATE`).

#### Scenario: Aprobación de un draft
- **WHEN** se recibe `PATCH /v1/prompts/{id}/status` con `status="approved"` sobre un prompt en `draft`
- **THEN** el prompt pasa a `approved` y se responde 200

#### Scenario: Deprecación de un approved
- **WHEN** se recibe `PATCH` con `status="deprecated"` sobre un prompt en `approved`
- **THEN** el prompt pasa a `deprecated` y se responde 200

#### Scenario: Reactivación de un deprecated
- **WHEN** se recibe `PATCH` con `status="approved"` sobre un prompt en `deprecated`
- **THEN** el prompt vuelve a `approved` y se responde 200

#### Scenario: Draft no es destino válido
- **WHEN** se recibe `PATCH` con `status="draft"` sobre un prompt en `approved` o `deprecated`
- **THEN** se responde 409 `INVALID_STATE_TRANSITION`

#### Scenario: Transición al mismo estado es rechazada
- **WHEN** se recibe `PATCH` con `status="approved"` sobre un prompt ya en `approved`
- **THEN** se responde 409 `INVALID_STATE_TRANSITION`

#### Scenario: Salto directo draft → deprecated es rechazado
- **WHEN** se recibe `PATCH` con `status="deprecated"` sobre un prompt en `draft`
- **THEN** se responde 409 `INVALID_STATE_TRANSITION`

### Requirement: Errores tipados y formato estándar
Los repositorios de prompts y transcripts SHALL señalizar los fallos con excepciones de dominio diferenciadas (inexistente, con ejecuciones, transición inválida) y los routers SHALL mapearlas a 404 `NOT_FOUND`, 409 `PROMPT_HAS_EXECUTIONS`/`TRANSCRIPT_HAS_EXECUTIONS` y 409 `INVALID_STATE_TRANSITION` respectivamente, usando el envelope de error estándar (`error.code`, `error.message`, `error.trace_id`).

#### Scenario: Formato de error en borrado rechazado
- **WHEN** un `DELETE` es rechazado con 409
- **THEN** el cuerpo contiene `error.code = "PROMPT_HAS_EXECUTIONS"` (o `TRANSCRIPT_HAS_EXECUTIONS`), un `error.message` legible y el `error.trace_id` del request

### Requirement: Migración de esquema reversible
Las columnas `deleted_at` (timestamp con zona, nullable) e `is_deleted` (boolean, not null, default false) SHALL añadirse a `prompts` y `transcripts` mediante una migración Alembic con `upgrade` y `downgrade` implementados, usando exclusivamente tipos SQLAlchemy portables. Las filas existentes SHALL quedar con `is_deleted=false`.

#### Scenario: Upgrade y downgrade
- **WHEN** se ejecuta `alembic upgrade head` seguido de `alembic downgrade -1`
- **THEN** ambas operaciones completan sin error y el esquema vuelve a su estado anterior
