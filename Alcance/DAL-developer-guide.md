# dal — Guía Técnica

## Visión general

`dal` (Database Abstraction Layer) es un microservicio FastAPI que actúa como la única capa del sistema con acceso directo a la base de datos. El resto de microservicios (backend, worker) consumen sus recursos vía HTTP interno en lugar de conectarse al DBMS directamente. Esto garantiza portabilidad entre motores (PostgreSQL, Oracle, SQL-Server, MySQL) y elimina estructuralmente el riesgo de SQL injection.

```
Backend ──► dal ──► PostgresProvider ──► PostgreSQL
Worker  ─────┘
```

El microservicio corre en el puerto `8002` y expone una API REST que refleja las entidades del sistema: prompts, versiones, ejecuciones, usuarios, transcripciones y conectores.

---

## Estructura del proyecto

```
dal/
├── app/
│   ├── config.py                  # Settings (pydantic-settings) + JSON logger
│   ├── database.py                # async_session_factory, get_session(), init_db()
│   ├── health.py                  # GET /health
│   ├── middleware/
│   │   ├── trace_id.py            # X-Trace-Id: lee o genera UUID, propaga en response
│   │   └── internal_auth.py      # Token auth en dev (MTLS_ENABLED=false)
│   ├── models/
│   │   └── schema.py              # 11 tablas SQLAlchemy Core + 6 índices
│   ├── providers/
│   │   ├── base.py                # BaseProvider (ABC): get_engine(), health_check()
│   │   ├── postgres.py            # PostgresProvider: asyncpg + pool
│   │   └── router.py              # Selecciona provider según DB_ENGINE
│   ├── repositories/
│   │   ├── prompts.py
│   │   ├── prompt_versions.py
│   │   ├── executions.py
│   │   ├── users.py
│   │   ├── transcripts.py
│   │   ├── transcript_versions.py
│   │   └── connectors.py
│   ├── routers/
│   │   ├── prompts.py
│   │   ├── executions.py
│   │   ├── users.py
│   │   ├── transcripts.py
│   │   ├── connectors.py
│   │   └── config.py
│   └── schemas/
│       ├── requests.py            # Pydantic input models con validators
│       └── responses.py           # SuccessResponse[T], ErrorResponse, entity models
├── tests/
│   ├── conftest.py                # Fixtures: db_engine, db_session (rollback), client
│   ├── test_prompts.py
│   ├── test_executions.py
│   └── test_users.py
├── main.py                        # Entrypoint: lifespan, middlewares, routers
├── Dockerfile
├── docker-compose.test.yml
├── requirements.txt
└── .env.example
```

---

## Arquitectura y decisiones de diseño

### Patrón Provider

El acceso al motor de base de datos está abstraído detrás de `BaseProvider`:

```python
class BaseProvider(ABC):
    @abstractmethod
    def get_engine(self) -> AsyncEngine: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
```

`providers/router.py` lee `DB_ENGINE` y retorna la implementación correspondiente. Para agregar soporte a un nuevo motor (Oracle, SQL-Server): crear una clase que herede de `BaseProvider`, registrarla en `router.py`. No es necesario tocar ningún repositorio ni endpoint.

### SQLAlchemy Core (no ORM declarativo)

El esquema usa `sqlalchemy.Table` + `MetaData` en lugar de `declarative_base()`. Esto es una decisión deliberada: SQLAlchemy Core es independiente del motor y garantiza que las queries generadas no usen features propietarios de ningún DBMS. Todos los campos de tiempo usan `DateTime(timezone=True)` y todos los IDs usan `UUID(as_uuid=True)`, tipos estándar de SQLAlchemy.

Los campos de estructura genuinamente variable (`input_data`, `output_data`, `config`, `system_config.value`) usan `JSONB` de `sqlalchemy.dialects.postgresql`. Al migrar a otro motor, estos campos son el único punto de adaptación.

### Patrón Repository

Cada entidad tiene su propio repositorio que:
- Acepta modelos Pydantic como input (`PromptCreate`, `VersionCreate`, etc.)
- Retorna modelos Pydantic como output (`PromptResponse`, `VersionResponse`, etc.)
- **Nunca** expone objetos `Row` de SQLAlchemy hacia los routers

```python
class PromptsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: PromptCreate) -> PromptResponse:
        row_id = uuid.uuid4()          # UUID generado en Python, nunca en el DBMS
        stmt = prompts.insert().values(id=row_id, ...).returning(*prompts.c)
        result = await self._session.execute(stmt)
        return _row_to_response(result.fetchone())
```

Los UUIDs se generan siempre en Python (`uuid.uuid4()`), nunca delegados a la función `gen_random_uuid()` del DBMS. Esto garantiza portabilidad entre motores.

### Inmutabilidad de versiones

Los campos `content` de `prompt_versions` y `transcript_versions` son inmutables. El repositorio nunca emite un `UPDATE` sobre ellos. Crear una nueva versión siempre inserta una fila nueva con `version_number` auto-incrementado.

La activación de una versión (`is_active=True`) es atómica: `_deactivate_all_in_tx()` y el `INSERT` de la nueva versión se ejecutan dentro de la misma `AsyncSession` sin commit intermedio:

```python
async def _deactivate_all_in_tx(self, prompt_id: UUID) -> None:
    stmt = (
        update(prompt_versions)
        .where(prompt_versions.c.prompt_id == prompt_id)
        .values(is_active=False)
    )
    await self._session.execute(stmt)
    # No commit aquí — el commit lo hace create() al final
```

### Middleware stack

Los middlewares se registran en `main.py` en orden inverso a su ejecución (Starlette los apila):

```
Solicitud entrante
    │
    ▼
TraceIdMiddleware      ← lee o genera X-Trace-Id, almacena en request.state.trace_id
    │
    ▼
InternalAuthMiddleware ← valida X-Internal-Service-Token (excepto /health)
    │
    ▼
Handler del endpoint
```

`TraceIdMiddleware` se registra después en código pero se ejecuta primero porque Starlette invierte el orden. Esto permite que `InternalAuthMiddleware` lea `request.state.trace_id` para incluirlo en las respuestas de error de autenticación.

### Autenticación interna

El DAL es un servicio interno que nunca recibe tráfico externo. En producción se protege con mTLS (mutual TLS): cada llamada al DAL presenta un certificado de cliente firmado por la CA interna del proyecto.

En entornos dev (`MTLS_ENABLED=false`), el middleware acepta el header `X-Internal-Service-Token` como mecanismo alternativo:

| Condición | Comportamiento |
|-----------|----------------|
| `MTLS_ENABLED=true` | Middleware pasa sin validar token |
| `MTLS_ENABLED=false` + token configurado | Valida `X-Internal-Service-Token` |
| `MTLS_ENABLED=false` + sin token configurado | Pasa sin autenticar (warning en startup) |
| Token configurado pero ausente en request | HTTP 401 `MISSING_SERVICE_TOKEN` |
| Token configurado pero incorrecto | HTTP 401 `INVALID_SERVICE_TOKEN` |

`/health` está siempre exento de autenticación para permitir health checks del orquestador.

### Propagación de Trace ID

Todo request que llega sin `X-Trace-Id` recibe uno generado como UUID v4. El valor queda en `request.state.trace_id` y se devuelve en el header `X-Trace-Id` de la respuesta. Los repositorios no necesitan leer este valor directamente; el logger lo recoge del contexto cuando se propaga via `extra={"trace_id": trace_id}`.

### Logging estructurado

`_JSONFormatter` en `config.py` serializa cada `LogRecord` a una línea JSON con campos fijos:

| Campo | Descripción |
|-------|-------------|
| `timestamp` | ISO 8601 UTC |
| `level` | `INFO`, `WARNING`, `ERROR` |
| `service` | Siempre `"dal"` |
| `trace_id` | UUID de la solicitud |
| `action` | Nombre de la operación (ej. `repo.prompts.create`) |
| `duration_ms` | Duración en milisegundos (si aplica) |
| `status` | `"ok"` o `"error"` |

El `safe_database_url` (`host:port/dbname`) se usa en los logs de arranque; la contraseña nunca aparece en ningún log.

### Envelope de respuesta

Todo endpoint retorna el mismo sobre:

```python
# Éxito
{"data": {...}, "meta": {"request_id": "uuid", "version": "1.0.0"}}

# Error
{"error": {"code": "NOT_FOUND", "message": "...", "trace_id": "uuid"}}
```

Los errores HTTP de FastAPI (422 de Pydantic, 404 de routers) retornan `{"detail": {"code": "...", "message": "..."}}` por coherencia con el manejador genérico de excepciones registrado en `main.py`.

---

## Flujo de un request de extremo a extremo

El sistema tiene dos fases de inicialización diferenciadas: el **arranque** (una vez al inicio) y el **procesamiento por request** (una vez por llamada). La selección del motor de base de datos ocurre en el arranque, no en cada request.

### Fase 1 — Arranque (lifespan)

Al arrancar el contenedor, antes de aceptar cualquier request:

```
main.py  lifespan()
    │
    ├─► warn_if_token_missing()          middleware/internal_auth.py
    │       Lee MTLS_ENABLED e INTERNAL_SERVICE_TOKEN
    │       Si ambos están vacíos → WARNING en log
    │
    └─► init_db()                        database.py
            │
            └─► get_provider(settings)   providers/router.py
                    │
                    │  Lee DB_ENGINE (variable de entorno)
                    │
                    ├─ "postgres" ──► PostgresProvider(settings)   providers/postgres.py
                    │                    create_async_engine(
                    │                      "postgresql+asyncpg://host:port/db"
                    │                      pool_size=DB_POOL_SIZE
                    │                      max_overflow=DB_MAX_OVERFLOW
                    │                    )
                    │
                    └─ otro valor ──► ValueError  (servicio no arranca)

            engine guardado en _engine (módulo database.py)
            async_session_factory = async_sessionmaker(_engine)
            metadata.create_all(engine)  →  crea tablas si no existen
```

La decisión de qué DBMS usar se toma **una sola vez aquí**. Todos los requests posteriores reutilizan el mismo engine y pool de conexiones.

---

### Fase 2 — Procesamiento de un request

```
 Cliente interno (backend / worker)
         │
         │  POST /v1/prompts
         │  Headers:
         │    X-Internal-Service-Token: <token>   (dev, MTLS_ENABLED=false)
         │    X-Trace-Id: <uuid>                  (opcional; lo genera el DAL si falta)
         │    Content-Type: application/json
         │
         ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  Uvicorn (ASGI)          main.py · port 8002                  │
 └──────────────────────────────┬────────────────────────────────┘
                                │
          Starlette apila middlewares en orden inverso al registro.
          add_middleware(InternalAuth) primero → ejecuta segundo.
          add_middleware(TraceId)     segundo → ejecuta primero.
                                │
                                ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  TraceIdMiddleware       middleware/trace_id.py               │
 │                                                               │
 │  ¿Viene X-Trace-Id en el request?                            │
 │    ├─ Sí → reutiliza el valor recibido                        │
 │    └─ No → genera uuid.uuid4()                                │
 │                                                               │
 │  request.state.trace_id = <uuid>                             │
 │  (disponible para todos los handlers y logs posteriores)      │
 └──────────────────────────────┬────────────────────────────────┘
                                │
                                ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  InternalAuthMiddleware  middleware/internal_auth.py          │
 │                                                               │
 │  ¿path == "/health"?                                          │
 │    └─ Sí → pasa sin validar (health checks del orquestador)  │
 │                                                               │
 │  ¿MTLS_ENABLED == true?                                       │
 │    └─ Sí → pasa (el certificado mTLS ya autenticó en la capa  │
 │             de red; no se valida token)                       │
 │                                                               │
 │  ¿INTERNAL_SERVICE_TOKEN configurado?                         │
 │    └─ No → pasa con warning (solo en dev sin token)           │
 │                                                               │
 │  ¿Header X-Internal-Service-Token presente?                   │
 │    ├─ No  → HTTP 401  MISSING_SERVICE_TOKEN                   │
 │    └─ Sí  → ¿coincide con INTERNAL_SERVICE_TOKEN?            │
 │               ├─ No  → HTTP 401  INVALID_SERVICE_TOKEN        │
 │               └─ Sí  → pasa                                   │
 └──────────────────────────────┬────────────────────────────────┘
                                │
                                ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  FastAPI — Router matching   routers/<entidad>.py             │
 │                                                               │
 │  /v1/prompts         → routers/prompts.py                     │
 │  /v1/prompts/{id}/…  → routers/prompts.py                     │
 │  /v1/executions      → routers/executions.py                  │
 │  /v1/users           → routers/users.py                       │
 │  /v1/transcripts     → routers/transcripts.py                 │
 │  /v1/connectors      → routers/connectors.py                  │
 │  /v1/config          → routers/config.py                      │
 │  /health             → health.py                              │
 │                                                               │
 │  Pydantic valida el body del request.                        │
 │  Si falla → HTTP 422 Unprocessable Entity (antes del handler) │
 └──────────────────────────────┬────────────────────────────────┘
                                │
                                │  FastAPI inyecta AsyncSession
                                │  via Depends(get_session)
                                │  ──► database.py · get_session()
                                │       └─ async_session_factory()
                                │           (pool pre-inicializado en arranque)
                                ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  Repository              repositories/<entidad>.py            │
 │                                                               │
 │  Acepta modelos Pydantic como input                          │
 │  Construye statement SQLAlchemy Core:                        │
 │    prompts.insert().values(...).returning(...)                │
 │    select(prompts).where(...)                                 │
 │    update(prompts).values(...).where(...)                     │
 │                                                               │
 │  await session.execute(stmt)                                  │
 │  await session.commit()                                       │
 │  Retorna modelos Pydantic como output                        │
 │  (nunca expone objetos Row de SQLAlchemy)                     │
 └──────────────────────────────┬────────────────────────────────┘
                                │
                                ▼
 ┌───────────────────────────────────────────────────────────────┐
 │  SQLAlchemy Core + asyncpg   providers/postgres.py            │
 │                                                               │
 │  AsyncEngine · pool de conexiones TCP                        │
 │  Las queries se compilan al dialecto PostgreSQL               │
 │  Los bind parameters previenen SQL injection estructuralmente │
 └──────────────────────────────┬────────────────────────────────┘
                                │
                                ▼
                     ┌─────────────────┐
                     │   PostgreSQL    │  port 5432
                     │   (contenedor   │  red vellum-internal
                     │    o externo)   │
                     └─────────────────┘
```

### Camino de retorno

La respuesta recorre el stack en sentido inverso:

```
PostgreSQL → asyncpg → SQLAlchemy Row → _row_to_response() → Pydantic model
    → SuccessResponse[T] (envelope estándar)
    → JSON serializado por FastAPI
    → TraceIdMiddleware añade X-Trace-Id al response header
    → Uvicorn envía HTTP response al cliente
```

### Punto de decisión del DBMS

```
                   DB_ENGINE (variable de entorno)
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
       "postgres"      "oracle"       "sqlserver"
           │          (futuro)        (futuro)
           ▼
   PostgresProvider    OracleProvider  SqlServerProvider
   (única implementación
    disponible hoy)
```

`providers/router.py:get_provider()` es el único lugar donde se toma esta decisión. El resto del sistema (repositorios, routers, middleware) no conoce ni importa qué motor está activo.

---

## Esquema de base de datos

### Tablas

| Tabla | Propósito |
|-------|-----------|
| `users` | Usuarios del sistema; `email` único, almacenado en minúsculas |
| `roles` | Roles de gobernanza (`viewer`, `service`, `approver`, `admin`) |
| `user_roles` | Tabla de unión N:N entre users y roles |
| `prompts` | Entidad principal de prompt; estados: `draft`, `approved`, `deprecated` |
| `prompt_versions` | Versiones inmutables de contenido; máximo una activa por prompt |
| `transcripts` | Entidad de transcripción de audio |
| `transcript_versions` | Versiones inmutables de contenido de transcripción |
| `executions` | Registro de cada ejecución de prompt; estados: `queued`, `running`, `completed`, `failed` |
| `connectors` | Conectores hacia sistemas externos |
| `connector_configs` | Configuración cifrada de cada conector (JSONB) |
| `system_config` | Clave-valor de configuración global del sistema (JSONB) |

### Índices

```python
Index("idx_prompt_versions_prompt_id_version_number", prompt_versions.c.prompt_id, prompt_versions.c.version_number)
Index("idx_executions_prompt_id",  executions.c.prompt_id)
Index("idx_executions_status",     executions.c.status)
Index("idx_executions_created_at", executions.c.created_at)
Index("idx_prompts_status",        prompts.c.status)
Index("idx_prompts_owner_id",      prompts.c.owner_id)
```

### Invariantes de datos

- `executions.completed_at` se setea automáticamente cuando el status pasa a `completed` o `failed`.
- `prompt_versions.content` y `transcript_versions.content` son de solo inserción; nunca se actualizan.
- Solo una versión por prompt puede tener `is_active=True` en cualquier momento.
- `users.email` se almacena y busca en minúsculas (`func.lower()`) para búsqueda case-insensitive.

---

## Configuración de entorno

### Variables requeridas

| Variable | Descripción | Requerida | Default |
|----------|-------------|:---------:|---------|
| `DB_HOST` | Host del servidor PostgreSQL | **Sí** | — |
| `DB_PORT` | Puerto del servidor | No | `5432` |
| `DB_NAME` | Nombre de la base de datos | **Sí** | — |
| `DB_USER` | Usuario de la base de datos | **Sí** | — |
| `DB_PASSWORD` | Contraseña del usuario | **Sí** | — |
| `DB_POOL_SIZE` | Tamaño del pool de conexiones | No | `10` |
| `DB_MAX_OVERFLOW` | Conexiones extra permitidas sobre el pool | No | `20` |
| `DB_POOL_TIMEOUT` | Timeout de adquisición de conexión (s) | No | `30` |
| `DB_ENGINE` | Motor a usar: `postgres` | No | `postgres` |
| `ENV` | Entorno: `dev`, `staging`, `prod` | No | `dev` |
| `MTLS_ENABLED` | Activa mTLS; desactiva validación por token | No | `false` |
| `MTLS_CERT_PATH` | Ruta al certificado del servicio | No | `/certs/dal.crt` |
| `MTLS_KEY_PATH` | Ruta a la clave privada | No | `/certs/dal.key` |
| `MTLS_CA_PATH` | Ruta al certificado de la CA interna | No | `/certs/ca.crt` |
| `INTERNAL_SERVICE_TOKEN` | Token de auth en dev (`MTLS_ENABLED=false`) | No | `""` |
| `LOG_LEVEL` | Nivel de log: `DEBUG`, `INFO`, `WARNING` | No | `INFO` |

```bash
cp dal/.env.example dal/.env
# Editar con los valores reales
```

---

## Despliegue

### Docker Compose (proyecto completo)

```bash
# Desde la raíz del proyecto
docker compose up -d postgres dal
```

El `docker-compose.yml` raíz define dos servicios:
- `postgres` — imagen `postgres:15-alpine`, volumen nombrado `postgres_data`, red interna `vellum-internal`
- `dal` — construido desde `dal/Dockerfile`, expuesto en el puerto `8002`, depende de `postgres`

### Dockerfile

La imagen usa `python:3.11-slim`. El healthcheck usa `urllib.request` de la librería estándar de Python (la imagen slim no incluye `curl`):

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1
```

El contenedor corre como usuario no-root (`appuser`).

---

## Ejecución de tests

Los tests requieren PostgreSQL. El `docker-compose.test.yml` levanta un PostgreSQL de test y el contenedor de tests en la misma red:

```bash
cd dal
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

O directamente con pytest si hay un PostgreSQL disponible:

```bash
# Con las variables de entorno configuradas en dal/.env
cd dal
pip install -r requirements.txt
pytest tests/ --cov=app --cov-report=term-missing -v
```

### Fixtures de test

`conftest.py` define tres fixtures:

| Fixture | Scope | Descripción |
|---------|-------|-------------|
| `db_engine` | session | Crea el engine, ejecuta `metadata.create_all`, cierra al final |
| `db_session` | function | Abre una transacción por test; hace rollback al terminar → aislamiento completo |
| `client` | function | `AsyncClient` con `ASGITransport`; sobreescribe `get_session` con la sesión de test |

El patrón de rollback garantiza que cada test parte de un estado limpio sin necesidad de truncar tablas.

---

## Añadir soporte a un nuevo motor de base de datos

1. Crear `dal/app/providers/nuevo_motor.py` heredando de `BaseProvider`.
2. Implementar `get_engine()` con `create_async_engine` y el driver correspondiente.
3. Implementar `health_check()` capturando todas las excepciones y retornando `bool`.
4. Registrar el motor en `providers/router.py` con su nombre en `DB_ENGINE`.
5. Agregar el driver en `requirements.txt`.
6. Verificar que los campos `JSONB` del esquema tienen equivalente en el nuevo motor (son el único punto de adaptación).

No es necesario modificar ningún repositorio, router ni middleware.
