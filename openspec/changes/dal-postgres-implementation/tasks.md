## 1. Project Scaffold

- [x] 1.1 Crear directorio `dal/` con la estructura completa de CA-01: `app/`, `app/config.py`, `app/database.py`, `app/middleware/`, `app/providers/`, `app/repositories/`, `app/models/`, `app/schemas/`, `app/routers/`, `app/health.py`, `tests/`
- [x] 1.2 Crear `dal/requirements.txt` con: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `asyncpg`, `pydantic>=2`, `httpx`, `pytest`, `pytest-asyncio`, `python-dotenv`
- [x] 1.3 Crear `dal/.env.example` con todas las variables documentadas según CA-09 (sin valores reales)
- [x] 1.4 Crear `dal/main.py` como entrypoint FastAPI que registra todos los routers, el middleware de trace_id y monta `/health`

## 2. Provider Interface

- [x] 2.1 Crear `dal/app/providers/base.py` con la clase abstracta `BaseProvider` según spec `dal-provider-interface`: métodos abstractos `get_engine() -> AsyncEngine` y `health_check() -> bool`
- [x] 2.2 Crear `dal/app/providers/router.py` que lee `DB_ENGINE` (default `postgres`) y retorna la implementación correspondiente; lanza `ValueError` para motores desconocidos

## 3. PostgreSQL Provider

- [x] 3.1 Crear `dal/app/config.py` con modelo Pydantic `Settings` que valida todas las variables de entorno requeridas (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, pool params, `MTLS_*`, `INTERNAL_SERVICE_TOKEN`, `ENV`, `LOG_LEVEL`)
- [x] 3.2 Crear `dal/app/providers/postgres.py` implementando `BaseProvider` con `create_async_engine` usando driver `asyncpg+postgresql`, DSN construido desde `Settings`, pool configurado desde variables de entorno
- [x] 3.3 Implementar `health_check()` en `PostgresProvider` que ejecuta `SELECT 1` y retorna `True`/`False` sin propagar excepciones
- [x] 3.4 Crear `dal/app/database.py` con `async_session_factory` usando `AsyncSession` sobre el engine del provider; exportar función `get_session()` como dependency de FastAPI

## 4. Database Schema

- [x] 4.1 Crear `dal/app/models/schema.py` con `MetaData` compartido y definir las 11 tablas usando `sqlalchemy.Table`: `users`, `roles`, `user_roles`, `prompts`, `prompt_versions`, `transcripts`, `transcript_versions`, `executions`, `connectors`, `connector_configs`, `system_config`
- [x] 4.2 Agregar todos los campos requeridos por la spec `dal-schema` incluyendo tipos correctos: UUID (VARCHAR/UUID nativo), TIMESTAMP WITH TIME ZONE, JSONB para campos variables
- [x] 4.3 Definir los 6 índices obligatorios con `sqlalchemy.Index`: `idx_prompt_versions_prompt_id_version_number`, `idx_executions_prompt_id`, `idx_executions_status`, `idx_executions_created_at`, `idx_prompts_status`, `idx_prompts_owner_id`
- [x] 4.4 Agregar función de inicialización en `database.py` que ejecuta `metadata.create_all` al arrancar (solo si las tablas no existen)

## 5. Pydantic Schemas

- [x] 5.1 Crear `dal/app/schemas/requests.py` con modelos de entrada: `PromptCreate`, `VersionCreate`, `ExecutionCreate`, `UserCreate`, `TranscriptCreate`, `ConnectorCreate`, `StatusUpdate` — todos con validadores Pydantic y `Literal` donde el campo tiene valores fijos
- [x] 5.2 Crear `dal/app/schemas/responses.py` con modelos de salida: `PromptResponse`, `VersionResponse`, `ExecutionResponse`, `UserResponse`, `TranscriptResponse`, `ConnectorResponse` — con tipos correctos para serialización JSON
- [x] 5.3 Crear modelos de envelope estándar: `SuccessResponse[T]` con campos `data` y `meta` (request_id, version), y `ErrorResponse` con campo `error` (code, message, trace_id)

## 6. Middleware

- [x] 6.1 Crear `dal/app/middleware/trace_id.py` con middleware ASGI que lee `X-Trace-Id`, genera UUID v4 si ausente, almacena en `request.state.trace_id`, y agrega el header al response
- [x] 6.2 Configurar logger JSON estructurado en `dal/app/config.py` o módulo `logging_config.py` que emita entradas con campos: `timestamp`, `level`, `trace_id`, `service`, `action`, `duration_ms`, `status`

## 7. Internal Auth Middleware

- [x] 7.1 Crear `dal/app/middleware/internal_auth.py` con middleware/dependency que verifica `X-Internal-Service-Token` cuando `MTLS_ENABLED=false`; retorna HTTP 401 con código de error estándar si falta o es incorrecto
- [x] 7.2 Eximir `/health` del middleware de autenticación interna
- [x] 7.3 Agregar warning en startup si `MTLS_ENABLED=false` y `INTERNAL_SERVICE_TOKEN` no está configurado

## 8. Repositories

- [x] 8.1 Crear `dal/app/repositories/prompts.py` con `PromptsRepository`: `create`, `get_by_id`, `list` (con filtros), `update_status`, `delete` — retornando siempre `PromptResponse | None`
- [x] 8.2 Crear `dal/app/repositories/prompt_versions.py` con `PromptVersionsRepository`: `create`, `get_by_id`, `list_by_prompt`, `get_active`, `deactivate_all` — la activación de nueva versión debe ejecutarse en una sola transacción con `deactivate_all`
- [x] 8.3 Crear `dal/app/repositories/executions.py` con `ExecutionsRepository`: `create`, `get_by_id`, `update_status` (setear `completed_at` en terminal states), `list_by_prompt`
- [x] 8.4 Crear `dal/app/repositories/users.py` con `UsersRepository`: `create`, `get_by_id`, `get_by_email` (case-insensitive), `assign_role` (con validación de existencia en transacción)
- [x] 8.5 Crear `dal/app/repositories/transcripts.py` y `transcript_versions.py` siguiendo la misma estructura que prompts/prompt_versions
- [x] 8.6 Crear `dal/app/repositories/connectors.py` con `ConnectorsRepository`: `create`, `get_by_id`, `list_active`, `set_active`

## 9. Routers

- [x] 9.1 Crear `dal/app/routers/prompts.py` con los 8 endpoints de prompts y versiones (POST `/v1/prompts`, GET `/v1/prompts/{id}`, GET `/v1/prompts`, PATCH status, POST/GET versiones, GET active)
- [x] 9.2 Crear `dal/app/routers/executions.py` con los 4 endpoints de ejecuciones
- [x] 9.3 Crear `dal/app/routers/users.py` con los 4 endpoints de usuarios incluyendo asignación de rol
- [x] 9.4 Crear `dal/app/routers/transcripts.py` con los 5 endpoints de transcripciones y versiones
- [x] 9.5 Crear `dal/app/routers/connectors.py` con los 4 endpoints de conectores
- [x] 9.6 Crear `dal/app/health.py` con endpoint `GET /health` que retorna estado del servicio y resultado de `health_check()`
- [x] 9.7 Crear router para `GET /v1/config` y `PUT /v1/config/{key}` (lectura/escritura de `system_config`)
- [x] 9.8 Verificar que todos los endpoints retornan el envelope estándar y los HTTP status codes correctos

## 10. Docker

- [x] 10.1 Crear `dal/Dockerfile` con imagen `python:3.11-slim`, usuario `appuser` no-root, `EXPOSE 8002`, `HEALTHCHECK` con curl a `/health`, `CMD uvicorn main:app --host 0.0.0.0 --port 8002`
- [x] 10.2 Agregar servicio `dal` y servicio `postgres` (imagen `postgres:15`) al `docker-compose.yml` raíz del proyecto con red interna nombrada y volumen nombrado para datos

## 11. Tests

- [x] 11.1 Crear `dal/tests/conftest.py` con fixture `db_engine` que usa PostgreSQL real (vía docker-compose.test.yml), crea todas las tablas al iniciar y las elimina al finalizar; fixture de transacción con rollback para aislamiento entre tests
- [x] 11.2 Crear `dal/docker-compose.test.yml` con servicio PostgreSQL 15 y servicio de tests
- [x] 11.3 Crear `dal/tests/test_prompts.py`: tests de `PromptsRepository` y endpoints de prompts/versiones (CRUD, filtros, activación atómica)
- [x] 11.4 Crear `dal/tests/test_executions.py`: tests de `ExecutionsRepository` y endpoints de ejecuciones (create, update_status con completed_at, list con filtros)
- [x] 11.5 Crear `dal/tests/test_users.py`: tests de `UsersRepository` y endpoints de usuarios (create, get_by_email case-insensitive, assign_role, conflicto 409)
- [ ] 11.6 Verificar cobertura ≥ 80% con `pytest --cov=app --cov-report=term-missing`

## 12. Verification

- [x] 12.1 Ejecutar `grep -r "SELECT\|INSERT\|UPDATE\|DELETE" dal/app/` y confirmar que no hay SQL crudo fuera de comentarios
- [x] 12.2 Ejecutar `grep -r "import psycopg2" dal/app/` y confirmar que psycopg2 solo aparece dentro de `providers/`
- [ ] 12.3 Construir imagen Docker (`docker build dal/`) y confirmar que arranca correctamente y `/health` responde
- [ ] 12.4 Revisar el checklist de Definition of Done de US-DAL-001 ítem por ítem
