# Design: dal-schema-migration-gate

## Context

El DAL ya tiene Alembic configurado (`dal/alembic.ini`, `dal/migrations/`) con una migración inicial (`20260531_a1b2c3d4e5f6_initial_schema.py`), y el lifespan de `dal/main.py` condiciona `metadata.create_all()` a `ENV == "dev"`. Sin embargo:

- En `staging`/`prod` el arranque no verifica nada: el servicio levanta contra una BD vacía o desfasada y falla en runtime con 500s.
- Nada en el `Dockerfile` ni en `docker-compose.yml` ejecuta `alembic upgrade head`; no existe un mecanismo operativo definido para aplicar migraciones.
- El healthcheck (`/health`) no toca la BD, por lo que un orquestador considera "sano" un DAL apuntando a un esquema inexistente.

Restricción de CLAUDE.md relevante: las migraciones se gestionan con Alembic, reversibles, y la app no debe alterar el esquema. Restricción de auditoría (bancaria): el esquema se cambia solo con control explícito y revisión humana.

## Goals / Non-Goals

**Goals:**
- Fail-fast en arranque en **todos los entornos**: el proceso no levanta si `alembic_version` ≠ head del código.
- Mecanismo operativo único y explícito para aplicar migraciones en todos los entornos: contenedor efímero `dal-migrate` que ejecuta `alembic upgrade head` y termina. `create_all` queda confinado a fixtures de tests.
- Separación estructural de privilegios en PostgreSQL: el servicio DAL se conecta con un usuario **sin permisos DDL**; solo el usuario de migraciones puede alterar el esquema. La garantía deja de depender del código.
- Flujo de despliegue documentado con gate de aprobación humana antes de migrar.
- Mensajes de error de arranque accionables (revisión actual vs. esperada, sin credenciales en logs).

**Non-Goals:**
- No se implementa pipeline CI/CD real (no hay uno en el repo); se define el contrato del paso y se materializa en docker-compose + runbook.
- No se cambian los fixtures de tests (`create_all` en `conftest.py` es legítimo: BD efímera de test).
- No se añade verificación de esquema al endpoint `/health` (el gate es de arranque, no de runtime).
- No se gestiona aún el aprovisionamiento de roles vía Secret Manager (Vault); en local/compose los roles se crean con script de init de PostgreSQL.

## Decisions

### D1 — Verificación por revisión de Alembic, no por inspección de tablas
`verify_schema_version()` compara `MigrationContext.get_current_revision()` (leído de la tabla `alembic_version` con la conexión async existente vía `run_sync`) contra `ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()`.

*Alternativa descartada*: inspeccionar que existan las tablas (`inspector.get_table_names()`). Detecta BD vacía pero no esquemas desfasados (columna añadida en una migración posterior), que es justo el caso peligroso.

### D2 — Abort por excepción en lifespan
Si la revisión no coincide (o `alembic_version` no existe → `get_current_revision()` retorna `None`), se lanza `RuntimeError` dentro del lifespan. Uvicorn aborta el arranque y el contenedor termina con exit code ≠ 0, lo que el orquestador interpreta como fallo de despliegue.

*Alternativa descartada*: loggear warning y arrancar en modo degradado. Contradice el requisito de la auditoría (fail-fast) y difiere el fallo a runtime.

### D3 — Contenedor efímero reutilizando la imagen del DAL
Nuevo servicio `dal-migrate` en `docker-compose.yml` que usa la misma imagen del DAL (`build: ./dal`) con `command: ["alembic", "upgrade", "head"]` y `profiles: ["migrate"]`, de modo que **no** arranca con `docker compose up` normal: solo con invocación explícita (`docker compose run --rm dal-migrate`). La imagen ya copia `alembic.ini` y `migrations/`, no requiere imagen nueva.

*Alternativas descartadas*:
- Entrypoint condicional (`RUN_MIGRATIONS=true && alembic upgrade head && uvicorn ...`): reintroduce "la app modifica el esquema al arrancar" y crea carrera con múltiples réplicas.
- Imagen Docker separada para migraciones: duplica build y deriva de versiones entre imagen de app y de migraciones.

### D4 — Gate de aprobación humana como contrato de proceso, no de código
El gate se materializa como: (1) el servicio `dal-migrate` nunca se ejecuta automáticamente (profile explícito), y (2) el runbook en `docs/DAL-developer-guide.md` define la secuencia aprobación → `docker compose run --rm dal-migrate` → desplegar DAL. Cuando exista un pipeline CI/CD real, el paso se mapea a un job con manual approval; el contrato (migrar es un paso separado, aprobado, previo al deploy) no cambia.

### D5 — Dev abandona `create_all`: Alembic en todos los entornos
**(Decisión actualizada tras revisión del arquitecto.)** El lifespan ejecuta `verify_schema_version()` en todos los entornos sin bifurcación por `ENV`; `init_db()`/`create_all` se elimina del servicio y queda solo en los fixtures de tests. El flujo de dev pasa a ser idéntico al de staging/prod: `docker compose run --rm dal-migrate` antes de levantar el DAL.

*Razón*: homologación de entornos — el flujo completo (incluido un `alembic upgrade`) se valida y prueba en desarrollo, y desaparece la deriva dev/staging (una tabla añadida a `schema.py` sin migración falla igual en todos los entornos). El coste es un comando extra en el setup local, mitigado documentándolo como primer paso del quickstart de dev.

*Alternativa descartada*: mantener `create_all` en dev por conveniencia. Crea dos mecanismos de creación de esquema, impide probar migraciones en dev y deja la deriva latente hasta staging.

### D6 — Usuarios de BD separados: servicio sin DDL, migrador con DDL
**(Decisión actualizada tras revisión del arquitecto: la garantía debe ser estructural, no solo de código.)** Se definen dos roles en PostgreSQL:

| Rol | Privilegios | Lo usa |
|---|---|---|
| `vellum_app` | `SELECT/INSERT/UPDATE/DELETE` sobre tablas del esquema; `USAGE` sobre secuencias. **Sin** `CREATE/ALTER/DROP` | Servicio DAL (`DB_USER`) |
| `vellum_migrator` | Owner del esquema: DDL completo | Contenedor `dal-migrate` (`DB_MIGRATIONS_USER`) |

Con esto, aunque una regresión de código reintrodujera DDL en el servicio, PostgreSQL lo rechazaría con `permission denied`.

Detalles de implementación:
- **Aprovisionamiento de roles**: script SQL idempotente montado en `docker-entrypoint-initdb.d/` del contenedor de PostgreSQL (se ejecuta una vez al crear el volumen). En entornos gestionados, el mismo script lo aplica el DBA. Crear roles **no** es responsabilidad de las migraciones Alembic (las migraciones asumen que los roles existen).
- **Grants sobre tablas futuras**: `ALTER DEFAULT PRIVILEGES FOR ROLE vellum_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vellum_app` (y `USAGE` sobre secuencias), de modo que cada tabla nueva creada por una migración queda accesible para el servicio sin grants manuales.
- **Configuración**: `Settings` del DAL sigue usando `DB_USER`/`DB_PASSWORD` (ahora `vellum_app`); el servicio `dal-migrate` recibe las credenciales del migrador vía variables de entorno propias (`DB_USER=vellum_migrator` en su `environment`/env_file). Mismo `Settings`, credenciales distintas por contenedor.
- La verificación de arranque solo necesita `SELECT` sobre `alembic_version`, cubierto por los privilegios de `vellum_app`.

*Alternativa descartada*: un único usuario con DDL para todo (estado actual). La prohibición de DDL en el servicio sería solo disciplina de código, exactamente lo que la auditoría señala como insuficiente en un entorno bancario.

## Risks / Trade-offs

- **[Riesgo] La verificación añade una dependencia de arranque a la BD: si la BD está caída, el DAL no levanta en staging/prod** → Es el comportamiento deseado (el DAL sin BD no es funcional), pero debe registrarse con un mensaje distinguible de "esquema desfasado" para no confundir diagnósticos. Reintentos de conexión quedan en manos del orquestador (restart policy).
- **[Riesgo] Operador olvida ejecutar `dal-migrate` antes de desplegar** → El fail-fast convierte el olvido en un fallo de despliegue explícito e inmediato con mensaje que indica el comando exacto a ejecutar.
- **[Riesgo] `alembic upgrade head` falla a mitad de migración** → Las migraciones del proyecto son reversibles por regla (upgrade+downgrade); PostgreSQL ejecuta DDL transaccional, por lo que una migración fallida hace rollback de sí misma. El runbook incluye el procedimiento de `alembic downgrade`.
- **[Trade-off] El setup de dev gana un paso obligatorio (`dal-migrate` antes de levantar)** → Aceptado conscientemente (D5): es el precio de la homologación de entornos. Se documenta como primer paso del quickstart; el mensaje de fail-fast indica el comando exacto.
- **[Riesgo] Volúmenes de PostgreSQL existentes no ejecutan `docker-entrypoint-initdb.d` (solo corre en la creación inicial)** → El script de roles es idempotente (`DO $$ ... IF NOT EXISTS`) y el runbook documenta cómo aplicarlo manualmente sobre una BD ya existente (`psql -f`).
- **[Riesgo] Una migración crea una tabla y el servicio no puede leerla (grants ausentes)** → Mitigado con `ALTER DEFAULT PRIVILEGES` en el script de roles (D6); el test end-to-end con los dos usuarios lo verifica.
- **[Riesgo] `ScriptDirectory` necesita localizar `alembic.ini`/`migrations/` en runtime dentro del contenedor** → La imagen ya los copia a `/app`; la verificación debe construir la ruta relativa al working dir de la app, y el test de arranque en Docker (tarea de validación) lo cubre.

## Migration Plan

1. Crear el script de roles (`vellum_app` / `vellum_migrator` + default privileges) y montarlo en el init de PostgreSQL; documentar su aplicación manual sobre BDs existentes.
2. Implementar `verify_schema_version()` y reemplazar `init_db()` en el lifespan (todos los entornos).
3. Añadir servicio `dal-migrate` con profile a `docker-compose.yml`, con credenciales de `vellum_migrator`; cambiar las credenciales del servicio DAL a `vellum_app`.
4. Validar en local el flujo completo: BD vacía + roles → arranque del DAL falla → `docker compose run --rm dal-migrate` → arranque OK; verificar que el usuario del servicio no puede ejecutar DDL.
5. Documentar el runbook de despliegue y el nuevo quickstart de dev en `docs/DAL-developer-guide.md`.

**Rollback**: revertir el cambio de lifespan restaura el comportamiento actual (arranque sin verificación). El servicio `dal-migrate` es inerte si no se invoca. Revertir los roles equivale a volver a conectar el servicio con el usuario original con DDL.

## Open Questions

*(Resueltas por el arquitecto el 2026-06-10):*
- ~~¿Usuario de BD separado para migraciones (con DDL) vs. servicio (sin DDL)?~~ → **Sí, en este change** (D6): la garantía debe ser estructural a nivel de permisos de PostgreSQL, no solo de código.
- ~~¿Debe dev abandonar `create_all` y usar `alembic upgrade head` también?~~ → **Sí, en este change** (D5): entornos homologados; el flujo completo de migración, incluido un upgrade con Alembic, se valida en desarrollo.
