# US-DAL-001 — Database Abstraction Layer (DAL) · Implementación PostgreSQL

**Épica:** Infraestructura de Persistencia  
**Componente:** `dal` (microservicio independiente)  
**Sprint:** 1  
**Prioridad:** Alta — bloqueante para el desarrollo del Backend  
**Estado:** Pendiente

---

## Historia de Usuario

**Como** desarrollador del backend de Vellum,  
**quiero** disponer de un microservicio DAL con una API FastAPI que abstraiga el acceso a PostgreSQL mediante SQLAlchemy Core,  
**para que** el backend pueda persistir y consultar todas las entidades del sistema sin escribir SQL crudo y sin acoplarse a un motor de base de datos específico.

---

## Contexto y Restricciones de Arquitectura

> ⚠️ Este microservicio es el **único** componente del sistema autorizado a:
> - Importar drivers de base de datos (`psycopg2-binary`)
> - Construir queries mediante SQLAlchemy
> - Conocer el DSN de conexión a la base de datos
>
> Ningún otro microservicio puede acceder directamente a la base de datos.  
> Toda comunicación hacia el DAL es mediante su API FastAPI interna sobre mTLS.  
> Ver `CLAUDE.md` secciones 2.1, 4 y 11.

---

## Criterios de Aceptación

### CA-01 — Estructura del proyecto

```
dal/
├── Dockerfile
├── requirements.txt
├── .env.example
├── main.py                    # entrypoint FastAPI
├── app/
│   ├── config.py              # configuración desde variables de entorno
│   ├── database.py            # engine, session factory, pool config
│   ├── middleware/
│   │   └── trace_id.py        # propagación X-Trace-Id obligatoria
│   ├── providers/
│   │   ├── base.py            # interfaz abstracta BaseProvider
│   │   └── postgres.py        # implementación PostgreSQL
│   ├── repositories/
│   │   ├── prompts.py
│   │   ├── prompt_versions.py
│   │   ├── executions.py
│   │   ├── users.py
│   │   ├── transcripts.py
│   │   ├── transcript_versions.py
│   │   └── connectors.py
│   ├── models/
│   │   └── schema.py          # definición de tablas SQLAlchemy (Table objects)
│   ├── schemas/
│   │   ├── requests.py        # modelos Pydantic de entrada
│   │   └── responses.py       # modelos Pydantic de salida
│   ├── routers/
│   │   ├── prompts.py
│   │   ├── executions.py
│   │   ├── users.py
│   │   ├── transcripts.py
│   │   └── connectors.py
│   └── health.py              # endpoint /health
└── tests/
    ├── conftest.py            # fixtures: engine de test, base de datos limpia
    ├── test_prompts.py
    ├── test_executions.py
    └── test_users.py
```

---

### CA-02 — Interfaz abstracta BaseProvider

El archivo `providers/base.py` define el contrato que toda implementación futura (Oracle, SQL-Server, MySQL) debe cumplir. La interfaz no contiene lógica concreta.

```python
from abc import ABC, abstractmethod
from sqlalchemy.engine import Engine

class BaseProvider(ABC):

    @abstractmethod
    def get_engine(self) -> Engine:
        """Retorna el engine SQLAlchemy configurado para este motor."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verifica conectividad con la base de datos."""
        ...
```

---

### CA-03 — Implementación PostgreSQL

`providers/postgres.py` implementa `BaseProvider` usando `psycopg2-binary`. El DSN se construye exclusivamente desde variables de entorno. Nunca se hardcodea ningún valor de conexión.

```python
# Variables de entorno requeridas:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=vellum
DB_USER=vellum_user
DB_PASSWORD=<secreto>
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
```

Pool de conexiones configurado con `QueuePool`. Los valores del pool deben ser configurables, nunca hardcodeados.

---

### CA-04 — Definición de tablas (schema.py)

Todas las tablas se definen usando `sqlalchemy.Table` con `MetaData`. No se usa ORM declarativo (`Base = declarative_base()`) para mantener compatibilidad máxima con otros motores en el futuro.

Tablas a implementar en esta historia:

| Tabla | Campos mínimos requeridos |
|---|---|
| `users` | id (UUID PK), username, email, is_active, created_at, updated_at |
| `roles` | id (UUID PK), name, description |
| `user_roles` | user_id (FK), role_id (FK), PK compuesta |
| `prompts` | id (UUID PK), name, description, owner_id (FK), status, visibility, created_at, updated_at |
| `prompt_versions` | id (UUID PK), prompt_id (FK), version_number, content, change_log, created_by (FK), created_at, is_active |
| `transcripts` | id (UUID PK), name, media_url, owner_id (FK), status, created_at, updated_at |
| `transcript_versions` | id (UUID PK), transcript_id (FK), version_number, content, change_log, created_by (FK), created_at, is_active |
| `executions` | id (UUID PK), prompt_id (FK), version_id (FK), transcript_id (FK nullable), executed_by (FK), input_data (JSONB), output_data (JSONB), status, model_used, cost, created_at, completed_at |
| `connectors` | id (UUID PK), type, name, is_active, created_at |
| `connector_configs` | id (UUID PK), connector_id (FK), config (JSONB), encrypted, created_at |
| `system_config` | key (VARCHAR PK), value (JSONB), updated_at |

Índices obligatorios a crear:

```sql
-- Traducción conceptual (se implementan con SQLAlchemy Index, no SQL crudo)
idx_prompt_versions_prompt_id_version_number
idx_executions_prompt_id
idx_executions_status
idx_executions_created_at
idx_prompts_status
idx_prompts_owner_id
```

---

### CA-05 — Repositories

Cada repository encapsula las operaciones de su entidad. No retornan objetos SQLAlchemy internos — retornan diccionarios o modelos Pydantic.

Operaciones mínimas por repository:

**PromptsRepository:**
- `create(data: PromptCreate) -> PromptResponse`
- `get_by_id(id: UUID) -> PromptResponse | None`
- `list(filters: PromptFilters) -> list[PromptResponse]`
- `update_status(id: UUID, status: str) -> PromptResponse`
- `delete(id: UUID) -> bool`

**PromptVersionsRepository:**
- `create(data: VersionCreate) -> VersionResponse`
- `get_by_id(id: UUID) -> VersionResponse | None`
- `list_by_prompt(prompt_id: UUID) -> list[VersionResponse]`
- `get_active(prompt_id: UUID) -> VersionResponse | None`
- `deactivate_all(prompt_id: UUID) -> None` (antes de activar una nueva versión)

**ExecutionsRepository:**
- `create(data: ExecutionCreate) -> ExecutionResponse`
- `get_by_id(id: UUID) -> ExecutionResponse | None`
- `update_status(id: UUID, status: str, output: dict | None) -> ExecutionResponse`
- `list_by_prompt(prompt_id: UUID, limit: int, offset: int) -> list[ExecutionResponse]`

**UsersRepository:**
- `create(data: UserCreate) -> UserResponse`
- `get_by_id(id: UUID) -> UserResponse | None`
- `get_by_email(email: str) -> UserResponse | None`
- `assign_role(user_id: UUID, role_id: UUID) -> None`

**TranscriptsRepository** y **TranscriptVersionsRepository**: misma estructura que Prompts/PromptVersions.

---

### CA-06 — Endpoints de la API FastAPI

Base URL interna: `http://dal:8002/v1`

```
Prompts:
  POST   /v1/prompts
  GET    /v1/prompts/{id}
  GET    /v1/prompts?status=&owner_id=&limit=&offset=
  PATCH  /v1/prompts/{id}/status

Versiones:
  POST   /v1/prompts/{id}/versions
  GET    /v1/prompts/{id}/versions
  GET    /v1/prompts/{id}/versions/active
  GET    /v1/prompts/{id}/versions/{version_id}

Ejecuciones:
  POST   /v1/executions
  GET    /v1/executions/{id}
  PATCH  /v1/executions/{id}/status
  GET    /v1/executions?prompt_id=&status=&limit=&offset=

Usuarios:
  POST   /v1/users
  GET    /v1/users/{id}
  GET    /v1/users/email/{email}
  POST   /v1/users/{id}/roles

Transcripciones:
  POST   /v1/transcripts
  GET    /v1/transcripts/{id}
  PATCH  /v1/transcripts/{id}/status
  POST   /v1/transcripts/{id}/versions
  GET    /v1/transcripts/{id}/versions/active

Conectores:
  POST   /v1/connectors
  GET    /v1/connectors
  GET    /v1/connectors/{id}
  PATCH  /v1/connectors/{id}/active

Sistema:
  GET    /health
  GET    /v1/config
  PUT    /v1/config/{key}
```

Todos los endpoints respetan el formato estándar de respuesta definido en `CLAUDE.md` sección 8.

---

### CA-07 — Seguridad interna del DAL

- El DAL no implementa autenticación de usuarios finales (eso es responsabilidad del backend).
- Sí valida que los requests provienen de servicios internos autorizados mediante mTLS o, en entorno dev, mediante un header `X-Internal-Service-Token` configurable por variable de entorno.
- El DSN completo con contraseña nunca aparece en logs. Loggear solo `host:port/dbname`.
- El campo `config` de `connector_configs` se almacena como recibido — el cifrado/descifrado es responsabilidad del backend, el DAL es agnóstico a eso.

---

### CA-08 — Propagación de Trace ID

El middleware de `trace_id.py` es obligatorio. Todo log generado por el DAL incluye el `X-Trace-Id` del request que lo originó. Formato de log estructurado JSON:

```json
{
  "timestamp": "2026-05-29T10:00:00Z",
  "level": "INFO",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "service": "dal",
  "action": "prompts.create",
  "duration_ms": 12,
  "status": "success"
}
```

---

### CA-09 — Variables de entorno requeridas

El archivo `.env.example` debe existir en el repositorio con todas las variables documentadas (sin valores reales):

```bash
# Base de datos
DB_HOST=
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# Entorno
ENV=dev                          # dev | staging | prod

# mTLS (obligatorio en staging y prod)
MTLS_ENABLED=false
MTLS_CERT_PATH=/certs/dal.crt
MTLS_KEY_PATH=/certs/dal.key
MTLS_CA_PATH=/certs/ca.crt

# Seguridad interna (solo dev)
INTERNAL_SERVICE_TOKEN=

# Logging
LOG_LEVEL=INFO
```

---

### CA-10 — Docker

`Dockerfile` con imagen `python:3.11-slim`. El proceso no corre como root.

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN adduser --disabled-password --gecos '' appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:8002/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

---

### CA-11 — Tests

- Tests con `pytest` usando una base de datos PostgreSQL real levantada en Docker (no mocks de SQLAlchemy).
- Fixture `db_engine` en `conftest.py`: crea todas las tablas al inicio y las destruye al finalizar.
- Cada test opera en una transacción que se revierte al terminar (rollback fixture), garantizando aislamiento sin truncar tablas.
- Cobertura mínima requerida: **80%** sobre los repositories y routers.

```bash
# Comando para correr tests
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

---

## Definición de Hecho (Definition of Done)

- [ ] Estructura de proyecto creada según CA-01
- [ ] `BaseProvider` implementado con contrato abstracto
- [ ] `PostgresProvider` implementado y conectando correctamente
- [ ] Todas las tablas del CA-04 definidas con SQLAlchemy Table objects
- [ ] Índices definidos en el schema
- [ ] Todos los repositories del CA-05 implementados
- [ ] Todos los endpoints del CA-06 implementados y funcionando
- [ ] Formato de respuesta estándar aplicado en todos los endpoints
- [ ] Middleware de trace_id activo
- [ ] Logs en formato JSON estructurado
- [ ] `.env.example` completo y documentado
- [ ] `Dockerfile` funcional, sin root, con healthcheck
- [ ] Tests corriendo contra PostgreSQL real (no mocks)
- [ ] Cobertura ≥ 80%
- [ ] Ninguna sentencia SQL cruda en el código (`grep -r "SELECT\|INSERT\|UPDATE\|DELETE" app/` retorna vacío fuera de comentarios)
- [ ] Ningún import de `psycopg2` fuera del directorio `providers/`

---

## Dependencias

| Dependencia | Estado |
|---|---|
| `router-ai` microservicio | ✅ Completado — no es bloqueante para esta historia |
| PostgreSQL 15 disponible en docker-compose | Requerido para desarrollo y tests |
| Redis | No requerido en esta historia |
| Backend | Bloqueado por esta historia |

---

## Notas Técnicas para el Agente de IA

- Usar `sqlalchemy` versión ≥ 2.0 (API unificada, no legacy).
- Usar `asyncpg` o `psycopg2-binary` según si el entorno es async o sync. Preferir async (`asyncpg`) para consistencia con FastAPI.
- Los UUIDs se generan siempre en la capa de aplicación (Python), nunca delegados a la base de datos, para garantizar portabilidad entre motores.
- El campo `status` de prompts acepta exactamente: `draft`, `approved`, `deprecated`. Validar con `Literal` de Pydantic.
- El campo `status` de executions acepta exactamente: `queued`, `running`, `completed`, `failed`.
- Las operaciones que afectan a `prompt_versions.is_active` deben ejecutarse en una única transacción: desactivar versión anterior y activar la nueva de forma atómica.
