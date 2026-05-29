## Why

El sistema Vellum carece de una capa de persistencia. El backend no puede almacenar ni consultar ninguna entidad (prompts, ejecuciones, usuarios) porque no existe un microservicio DAL que abstraiga el acceso a la base de datos. Sin el DAL, el desarrollo del backend queda completamente bloqueado.

## What Changes

- Nuevo microservicio `dal` con API FastAPI interna en el puerto 8002
- Implementación del proveedor PostgreSQL (primera implementación del patrón multi-motor)
- Interfaz abstracta `BaseProvider` que define el contrato para futuros motores (Oracle, SQL-Server, MySQL)
- Definición completa del schema de base de datos (11 tablas) mediante SQLAlchemy Core
- Repositories para todas las entidades: prompts, versiones de prompts, ejecuciones, usuarios, transcripciones y conectores
- Middleware obligatorio de propagación de `X-Trace-Id`
- Autenticación interna vía mTLS (staging/prod) o header `X-Internal-Service-Token` (dev)
- Dockerfile con usuario no-root y healthcheck
- Tests contra PostgreSQL real (sin mocks), cobertura ≥ 80%

## Capabilities

### New Capabilities

- `dal-provider-interface`: Interfaz abstracta `BaseProvider` que todos los proveedores de motor de base de datos deben implementar
- `dal-postgres-provider`: Implementación del proveedor PostgreSQL con SQLAlchemy Core, pool de conexiones y asyncpg
- `dal-schema`: Definición de todas las tablas del sistema (users, roles, user_roles, prompts, prompt_versions, transcripts, transcript_versions, executions, connectors, connector_configs, system_config) con índices
- `dal-repositories`: Repositories para prompts, prompt_versions, executions, users, transcripts, transcript_versions y connectors con operaciones CRUD
- `dal-api`: Endpoints FastAPI REST para todas las entidades (prompts, versiones, ejecuciones, usuarios, transcripciones, conectores, configuración de sistema) siguiendo el formato de respuesta estándar
- `dal-internal-auth`: Validación de que los requests provienen de servicios internos autorizados (mTLS o token en dev)
- `dal-trace-middleware`: Middleware de propagación y generación de `X-Trace-Id` con logging estructurado JSON

### Modified Capabilities

## Impact

- **Nuevo microservicio**: `dal/` — directorio nuevo, proceso independiente, Dockerfile propio
- **Bloqueante desbloqueado**: el microservicio `backend` puede ahora desarrollarse al tener un DAL disponible
- **Dependencias nuevas**: `fastapi`, `uvicorn`, `sqlalchemy>=2.0`, `asyncpg`, `psycopg2-binary`, `pydantic>=2`, `pytest`, `httpx`
- **Base de datos**: PostgreSQL 15, requiere estar disponible en `docker-compose` para desarrollo y tests
- **Red Docker interna**: el DAL escucha en `dal:8002`, solo accesible desde la red interna Docker
- **Sin impacto** en `router-ai`, `frontend`, `worker`, `conector-in`, `conector-out` o `gateway` en esta historia
