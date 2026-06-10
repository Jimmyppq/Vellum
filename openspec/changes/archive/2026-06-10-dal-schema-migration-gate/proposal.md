# Proposal: dal-schema-migration-gate

## Why

La auditoría del 31 de mayo marcó como **crítico y bloqueante para staging** que el DAL ejecuta `metadata.create_all()` en el lifespan de arranque: un reinicio de contenedor podía alterar el esquema de base de datos en caliente. El gating a `ENV == "dev"` ya se aplicó en `dal/main.py`, pero la segunda mitad de la recomendación sigue pendiente: **en staging/prod el arranque debe fallar si el esquema no está migrado al head de Alembic**, y las migraciones deben ejecutarse como un paso de despliegue explícito con aprobación humana — nunca desde el servicio en ejecución.

Hoy, un DAL desplegado contra una base de datos sin migrar arranca sin error, pasa el healthcheck (que no toca la BD) y falla con errores 500 en runtime cuando una query toca una tabla inexistente. El fallo se difiere al peor momento posible.

## What Changes

- Nueva función `verify_schema_version()` en el DAL: compara la revisión registrada en `alembic_version` contra el head de `migrations/versions/` y lanza error si no coinciden o si la tabla no existe.
- **BREAKING (flujo de dev)**: el lifespan de `dal/main.py` ejecuta `verify_schema_version()` en **todos los entornos** y **aborta el arranque** (fail-fast, uvicorn no levanta) si el esquema no está en head. `create_all()` desaparece del servicio y queda confinado a los fixtures de tests; en dev hay que ejecutar las migraciones antes de levantar el DAL.
- Nuevo servicio efímero `dal-migrate` en la infraestructura Docker: contenedor que ejecuta `alembic upgrade head` y termina. Es el **único** mecanismo que aplica DDL en cualquier entorno.
- **Separación estructural de privilegios en PostgreSQL**: el servicio DAL se conecta con un rol `vellum_app` sin permisos DDL; el contenedor `dal-migrate` usa un rol `vellum_migrator` owner del esquema. Aunque una regresión de código reintrodujera DDL en el servicio, PostgreSQL lo rechazaría.
- Script SQL idempotente de aprovisionamiento de roles (init de PostgreSQL en compose; aplicable manualmente por el DBA en entornos gestionados), incluyendo `ALTER DEFAULT PRIVILEGES` para que las tablas creadas por migraciones queden accesibles al servicio.
- El pipeline/runbook de despliegue queda definido como: (1) gate de aprobación humana → (2) ejecutar contenedor `dal-migrate` → (3) desplegar/reiniciar el servicio DAL. Documentado en el developer guide del DAL, junto con el nuevo quickstart de dev.

## Capabilities

### New Capabilities
- `dal-schema-migrations`: gobierno del ciclo de vida del esquema — verificación fail-fast de la revisión de Alembic en arranque (todos los entornos), ejecución de migraciones mediante contenedor efímero como paso de despliegue separado con aprobación humana, separación de roles de BD (servicio sin DDL / migrador con DDL), y restricción de `create_all` a fixtures de tests.

### Modified Capabilities
<!-- Sin cambios de requisitos en capacidades existentes: dal-schema define la estructura de tablas, no su mecanismo de aplicación. -->

## Impact

- **Código**: `dal/main.py` (lifespan), `dal/app/database.py` (nueva `verify_schema_version()`, eliminación de `init_db()`), sin cambios en repositorios ni routers.
- **Infraestructura**: `docker-compose.yml` (nuevo servicio efímero `dal-migrate` con profile/run manual, credenciales separadas por contenedor), script SQL de roles montado en el init de PostgreSQL, `dal/Dockerfile` (la imagen ya incluye Alembic y `migrations/`; el contenedor efímero reutiliza la misma imagen con comando distinto).
- **Base de datos**: dos roles nuevos (`vellum_app`, `vellum_migrator`); las credenciales actuales del servicio se sustituyen por las de `vellum_app`. En volúmenes de PostgreSQL existentes el script de roles debe aplicarse manualmente.
- **Operación**: nuevo paso obligatorio en todo despliegue y en el setup de dev (`alembic upgrade head` vía contenedor efímero; en staging/prod tras aprobación humana). Documentado en `docs/DAL-developer-guide.md`.
- **Riesgo de regresión**: moderado en dev (cambia el flujo de arranque: requiere migrar antes de levantar); en staging/prod el cambio convierte fallos diferidos en runtime en fallos explícitos de arranque.
- **Resuelve**: hallazgo crítico nº1 del DAL en `auditorias/AUDITORIA 31-may.md`.
