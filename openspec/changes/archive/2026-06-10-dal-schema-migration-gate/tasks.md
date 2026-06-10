# Tasks: dal-schema-migration-gate

## 1. Roles de base de datos (garantía estructural)

- [x] 1.1 Crear script SQL idempotente de aprovisionamiento: roles `vellum_app` (sin DDL: `SELECT/INSERT/UPDATE/DELETE` sobre tablas, `USAGE` sobre secuencias) y `vellum_migrator` (owner del esquema, DDL completo), con `ALTER DEFAULT PRIVILEGES FOR ROLE vellum_migrator` para tablas y secuencias futuras
- [x] 1.2 Montar el script en `docker-entrypoint-initdb.d/` del servicio PostgreSQL en `docker-compose.yml`
- [x] 1.3 Documentar la aplicación manual del script sobre volúmenes/BDs ya existentes (`psql -f`), dado que el init solo corre en la creación del volumen

## 2. Verificación de esquema en el DAL

- [x] 2.1 Implementar `verify_schema_version()` en `dal/app/database.py`: leer revisión actual con `MigrationContext.get_current_revision()` vía `conn.run_sync()` y compararla con `ScriptDirectory.from_config(...).get_current_head()`
- [x] 2.2 Distinguir los tres modos de fallo con mensajes accionables: BD no alcanzable (error de conexión, sin DSN con password), tabla `alembic_version` ausente ("esquema no migrado, ejecutar `docker compose run --rm dal-migrate`"), revisión desfasada (incluir revisión actual vs. head esperada)
- [x] 2.3 Modificar el lifespan de `dal/main.py`: ejecutar `await verify_schema_version()` en todos los entornos, sin bifurcación por `ENV`; eliminar `init_db()` de `database.py` y su import en `main.py` (el `create_all` de `tests/conftest.py` se mantiene)
- [x] 2.4 Loggear el resultado de la verificación con el formato JSON estructurado existente (action, status, mensaje), sin datos sensibles

## 3. Contenedor efímero de migraciones

- [x] 3.1 Añadir servicio `dal-migrate` a `docker-compose.yml`: misma build que `dal`, `command: ["alembic", "upgrade", "head"]`, `profiles: ["migrate"]`, red interna, `depends_on: postgres`, y credenciales de `vellum_migrator` (env propio, distinto del env del servicio)
- [x] 3.2 Cambiar las credenciales del servicio `dal` a `vellum_app` (`.env`/`env_file`) y verificar que ningún contenedor de servicio recibe las credenciales del migrador
- [x] 3.3 Verificar que la imagen del DAL incluye `alembic.ini` y `migrations/` en el working dir y que `alembic upgrade head` resuelve rutas correctamente dentro del contenedor

## 4. Tests

- [x] 4.1 Test unitario: `verify_schema_version()` pasa cuando la revisión de BD coincide con head
- [x] 4.2 Test unitario: `verify_schema_version()` lanza error cuando `alembic_version` no existe y cuando la revisión está desfasada, con los mensajes esperados
- [x] 4.3 Test de lifespan: con BD sin migrar, la app no arranca en ningún entorno; con BD migrada a head, arranca
- [x] 4.4 Test de permisos: una conexión como `vellum_app` recibe `permission denied` al intentar `CREATE TABLE`/`ALTER TABLE`/`DROP TABLE`
- [x] 4.5 Ejecutar la suite completa del DAL (`pytest`) y confirmar que los fixtures con `create_all` sobre la BD de test siguen funcionando

## 5. Validación end-to-end en Docker

- [x] 5.1 Con volumen de PostgreSQL nuevo: el init crea los roles; `docker compose up dal` con BD vacía falla con exit code ≠ 0 y mensaje de esquema no migrado
- [x] 5.2 Ejecutar `docker compose run --rm dal-migrate` → termina con exit code 0, `alembic_version` queda en head y las tablas pertenecen a `vellum_migrator`
- [x] 5.3 Re-arrancar el DAL → arranca correctamente como `vellum_app`, `/health` responde y los endpoints CRUD funcionan (grants por default privileges verificados)
- [x] 5.4 Confirmar que `docker compose up` normal no ejecuta `dal-migrate` (profile) y que el contenedor del servicio no tiene credenciales del migrador
- [x] 5.5 Probar el flujo de upgrade en dev: crear una migración dummy, aplicarla con `dal-migrate` sobre la BD ya poblada y verificar que el DAL la exige antes de arrancar (luego descartar la migración dummy)

## 6. Documentación

- [x] 6.1 Documentar en `docs/DAL-developer-guide.md` el runbook de despliegue staging/prod: gate de aprobación humana → `docker compose run --rm dal-migrate` → desplegar/reiniciar el DAL, incluyendo procedimiento de rollback con `alembic downgrade`
- [x] 6.2 Documentar el nuevo quickstart de dev: levantar PostgreSQL → `dal-migrate` → levantar DAL; y la regla de que todo cambio en `schema.py` requiere su migración Alembic correspondiente
- [x] 6.3 Documentar el modelo de roles de BD (qué rol usa cada contenedor, cómo aprovisionarlos en entornos gestionados)
- [x] 6.4 Marcar como resuelto el hallazgo crítico nº1 del DAL en el seguimiento de `auditorias/AUDITORIA 31-may.md` (o anotar la referencia al change)
