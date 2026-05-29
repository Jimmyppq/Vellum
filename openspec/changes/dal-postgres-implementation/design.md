## Context

Vellum es un sistema corporativo de gestión de prompts compuesto por microservicios. El contrato arquitectónico del proyecto (CLAUDE.md) prohibe que cualquier componente que no sea el `dal` acceda directamente a la base de datos. El `dal` es el primer microservicio de persistencia que se construye; su diseño sienta el patrón que seguirán futuras implementaciones para otros motores (Oracle, SQL-Server, MySQL).

El estado actual es: no existe directorio `dal/`, no existe ninguna capa de acceso a datos, el `backend` está bloqueado. Esta historia construye el DAL completo para PostgreSQL como primer motor.

## Goals / Non-Goals

**Goals:**

- Implementar el microservicio `dal` con API FastAPI en puerto 8002
- Definir la interfaz `BaseProvider` que todos los motores futuros heredarán
- Implementar `PostgresProvider` con SQLAlchemy Core ≥ 2.0 y `asyncpg` (modo async)
- Definir el schema completo (11 tablas + índices) con `sqlalchemy.Table` objects
- Implementar repositories para todas las entidades con operaciones CRUD mínimas
- Exponer los endpoints REST documentados en CA-06 con formato de respuesta estándar
- Validar origin de requests: mTLS en staging/prod, token en dev
- Propagar `X-Trace-Id` en todos los requests y logs
- Proveer Dockerfile sin root, healthcheck, y `.env.example` completo
- Tests con PostgreSQL real, cobertura ≥ 80%

**Non-Goals:**

- Implementar motores Oracle, SQL-Server, MySQL (quedan para historias futuras)
- Autenticación de usuarios finales (responsabilidad del `backend`)
- Cifrado/descifrado de `connector_configs.config` (responsabilidad del `backend`)
- Caché de queries (responsabilidad del `backend` con Redis)
- Sharding o réplicas de lectura
- Soporte a MongoDB

## Decisions

### D1 — SQLAlchemy Core (no ORM declarativo)

**Decisión:** Usar `sqlalchemy.Table` con `MetaData`, no `declarative_base()`.

**Rationale:** El ORM declarativo de SQLAlchemy genera SQL que puede usar features propietarios de un motor. SQLAlchemy Core con expresiones explícitas garantiza portabilidad máxima entre PostgreSQL, Oracle, SQL-Server y MySQL desde el primer día. El coste de verbosidad es aceptable dado que hay repositories que encapsulan la complejidad.

**Alternativa rechazada:** ORM declarativo — más ergonómico pero introduce dependencias silenciosas en tipos PostgreSQL (JSONB nativo, arrays, etc.).

---

### D2 — asyncpg como driver async (no psycopg2 síncrono)

**Decisión:** Usar `asyncpg` como driver de PostgreSQL para compatibilidad nativa con FastAPI async.

**Rationale:** FastAPI es completamente async. Usar psycopg2 síncrono requeriría `run_in_executor` en cada query, degradando rendimiento y complicando el código. `asyncpg` con SQLAlchemy async (`create_async_engine`) es el patrón oficial de SQLAlchemy 2.0.

**Alternativa rechazada:** `psycopg2-binary` síncrono — viable pero impone overhead de thread pool y no es el patrón recomendado en FastAPI.

---

### D3 — UUIDs generados en Python, no en la base de datos

**Decisión:** Los UUIDs se generan en Python con `uuid.uuid4()` antes de insertar en la base de datos.

**Rationale:** Portabilidad. La función `gen_random_uuid()` es PostgreSQL-specific. Al generar UUIDs en Python, el mismo código funciona en todos los motores sin modificación.

---

### D4 — Patrón Repository sobre SQLAlchemy, retornando Pydantic models

**Decisión:** Cada repository recibe y retorna modelos Pydantic, nunca objetos `Row` de SQLAlchemy.

**Rationale:** Los routers FastAPI trabajan con Pydantic. Exponer objetos SQLAlchemy a la capa de routers crea acoplamiento entre la persistencia y la serialización. Los repositories actúan como anti-corruption layer.

---

### D5 — Autenticación interna por entorno

**Decisión:** mTLS en staging/prod; header `X-Internal-Service-Token` en dev.

**Rationale:** mTLS es el estándar del proyecto (CLAUDE.md sección 3). Sin embargo, configurar certificados en entorno local es fricción innecesaria para desarrollo. El token de entorno dev es configurable por variable de entorno y nunca se hardcodea.

---

### D6 — Logs JSON estructurados con trace_id, sin datos sensibles

**Decisión:** Todo log emitido por el DAL es JSON con campos fijos (`timestamp`, `level`, `trace_id`, `service`, `action`, `duration_ms`, `status`). El DSN completo nunca aparece en logs.

**Rationale:** El DAL es el componente con mayor riesgo de filtrar credenciales (DSN) o PII (contenido de prompts). El formato estructurado facilita ingesta en sistemas de observabilidad (Loki, CloudWatch, etc.).

## Risks / Trade-offs

- **[Riesgo] asyncpg + SQLAlchemy 2.0 async tiene curva de aprendizaje en gestión de transacciones** → Mitigación: el `conftest.py` de tests incluye fixture de transacción con rollback automático; la documentación interna incluye ejemplo canónico de sesión async.

- **[Riesgo] La tabla `executions` crecerá masivamente** → Mitigación: CA-04 especifica particionado por `created_at` desde el inicio. Se implementa como parte del schema inicial.

- **[Trade-off] SQLAlchemy Core es más verboso que ORM** → Aceptado conscientemente. La ganancia en portabilidad entre motores es el objetivo central del DAL.

- **[Riesgo] Tests requieren PostgreSQL real disponible en CI** → Mitigación: `docker-compose.test.yml` levanta PostgreSQL 15 como servicio; el fixture `db_engine` gestiona ciclo de vida completo.

- **[Riesgo] `connector_configs.config` almacena datos cifrados como JSONB opaco** → El DAL no conoce la clave de cifrado, es completamente agnóstico. Si el backend falla en cifrar, el DAL almacena texto plano sin saberlo. Mitigación: el campo tiene flag `encrypted` boolean como indicador de contrato.

## Migration Plan

1. Crear directorio `dal/` con la estructura de CA-01
2. Levantar PostgreSQL 15 en `docker-compose.yml` del proyecto (nuevo servicio)
3. El DAL crea las tablas al arrancar si no existen (primera vez: `metadata.create_all`)
4. Las migraciones incrementales futuras se gestionan con Alembic (fuera de scope de esta historia)
5. El `backend` puede apuntar al DAL en `http://dal:8002` una vez que el contenedor esté healthy

**Rollback:** El DAL es un servicio nuevo; rollback = no desplegar. No hay datos existentes que perder.

## Open Questions

- ¿Se particionará `executions` por rango de fecha en la creación inicial del schema o se deja para una migración Alembic posterior? (La US dice "desde el inicio" — se implementa en `schema.py`)
- ¿El `docker-compose.yml` raíz del proyecto ya incluye una red interna nombrada, o hay que crearla en esta historia?
