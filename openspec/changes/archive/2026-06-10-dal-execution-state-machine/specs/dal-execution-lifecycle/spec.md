# dal-execution-lifecycle

## ADDED Requirements

### Requirement: Máquina de estados de ejecuciones
El DAL SHALL aplicar una máquina de estados explícita sobre `executions.status` con los estados `queued`, `running`, `completed`, `failed`, `cancelled` y exclusivamente estas transiciones: `queued → running`, `running → completed`, `running → failed`, `queued → cancelled`. Los estados `completed`, `failed` y `cancelled` SHALL ser terminales e inmutables. Toda ejecución SHALL crearse en estado `queued`.

#### Scenario: Transición válida queued → running
- **WHEN** se recibe `PATCH /v1/executions/{id}/status` con `status="running"` sobre una ejecución en `queued`
- **THEN** la ejecución pasa a `running` y se responde 200 con la ejecución actualizada

#### Scenario: Transición válida running → completed
- **WHEN** se recibe `PATCH` con `status="completed"` sobre una ejecución en `running`
- **THEN** la ejecución pasa a `completed`, se escribe `completed_at` en UTC y se responde 200

#### Scenario: Transición válida running → failed
- **WHEN** se recibe `PATCH` con `status="failed"` sobre una ejecución en `running`
- **THEN** la ejecución pasa a `failed`, se escribe `completed_at` y se responde 200

#### Scenario: Cancelación solo desde queued
- **WHEN** se recibe `PATCH` con `status="cancelled"` sobre una ejecución en `queued`
- **THEN** la ejecución pasa a `cancelled`, se escribe `completed_at` y se responde 200

#### Scenario: Cancelación de una ejecución running es rechazada
- **WHEN** se recibe `PATCH` con `status="cancelled"` sobre una ejecución en `running`
- **THEN** se responde 409 con código `INVALID_STATE_TRANSITION` y la ejecución no se modifica

### Requirement: Rechazo estricto de transiciones inválidas
El DAL SHALL responder HTTP 409 con código de error `INVALID_STATE_TRANSITION` ante cualquier transición no listada en la máquina de estados, incluida la transición de un estado a sí mismo (sin no-op idempotente). El mensaje de error SHALL incluir el estado actual y el solicitado. La ejecución SHALL permanecer sin modificar.

#### Scenario: Estado terminal es inmutable
- **WHEN** se recibe `PATCH` con `status="running"` sobre una ejecución en `failed`
- **THEN** se responde 409 `INVALID_STATE_TRANSITION` y la ejecución conserva `failed`, su `completed_at` y su `output_data`

#### Scenario: Transición al mismo estado es rechazada
- **WHEN** se recibe `PATCH` con `status="running"` sobre una ejecución ya en `running`
- **THEN** se responde 409 `INVALID_STATE_TRANSITION` (el cliente que reintenta tras un timeout SHALL verificar con `GET` en lugar de re-enviar el PATCH)

#### Scenario: Retorno a queued es rechazado
- **WHEN** se recibe `PATCH` con `status="queued"` sobre una ejecución en cualquier estado
- **THEN** se responde 409 `INVALID_STATE_TRANSITION`

#### Scenario: Ejecución inexistente
- **WHEN** se recibe `PATCH /v1/executions/{id}/status` con un `id` que no existe
- **THEN** se responde 404 con código `NOT_FOUND`

### Requirement: Aplicación atómica de transiciones
El DAL SHALL aplicar la transición mediante compare-and-set atómico: el `UPDATE` SHALL incluir en su cláusula `WHERE` el conjunto de estados origen permitidos para el destino solicitado, de modo que bajo concurrencia como máximo una de varias transiciones simultáneas tenga efecto. La construcción SHALL ser portable entre PostgreSQL, Oracle, SQL Server y MySQL/MariaDB (SQLAlchemy Core con bind parameters, sin features propietarios).

#### Scenario: Transiciones concurrentes sobre la misma ejecución
- **WHEN** dos requests simultáneos envían `status="running"` sobre la misma ejecución en `queued`
- **THEN** exactamente uno responde 200 y el otro responde 409 `INVALID_STATE_TRANSITION`

### Requirement: Datos de resultado solo en transiciones terminales
El DAL SHALL aceptar `output_data` y `cost` en el cuerpo de la actualización de status únicamente cuando el estado destino es terminal (`completed`, `failed`, `cancelled`). Si se incluyen en una transición no terminal, el DAL SHALL responder 400 con código `INVALID_PAYLOAD_FOR_TRANSITION` sin aplicar la transición. En toda transición terminal el DAL SHALL escribir `completed_at` con el timestamp UTC actual; `completed_at`, `output_data` y `cost` SHALL ser inescribibles por cualquier otro camino.

#### Scenario: Output y coste al completar
- **WHEN** se recibe `PATCH` con `status="completed"`, `output_data` y `cost` sobre una ejecución en `running`
- **THEN** se persisten `output_data`, `cost` y `completed_at` y se responde 200

#### Scenario: Output en transición no terminal es rechazado
- **WHEN** se recibe `PATCH` con `status="running"` y `output_data` sobre una ejecución en `queued`
- **THEN** se responde 400 `INVALID_PAYLOAD_FOR_TRANSITION` y la ejecución permanece en `queued`

#### Scenario: Transición terminal sin payload opcional
- **WHEN** se recibe `PATCH` con `status="failed"` sin `output_data` ni `cost` sobre una ejecución en `running`
- **THEN** la transición se aplica, `completed_at` se escribe y `output_data`/`cost` quedan como estaban (NULL)

### Requirement: Errores tipados del repositorio
El repositorio de ejecuciones SHALL señalizar los fallos con excepciones de dominio diferenciadas (ejecución inexistente vs. transición inválida) en lugar de `ValueError` genérico, y el router SHALL mapearlas a 404 `NOT_FOUND` y 409 `INVALID_STATE_TRANSITION` respectivamente, usando el formato de error estándar del sistema (`error.code`, `error.message`, `error.trace_id`).

#### Scenario: Formato de error en transición inválida
- **WHEN** una transición es rechazada con 409
- **THEN** el cuerpo de la respuesta contiene `error.code = "INVALID_STATE_TRANSITION"`, un `error.message` legible con el estado actual y el solicitado, y el `error.trace_id` del request
