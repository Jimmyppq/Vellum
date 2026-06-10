#!/bin/sh
# Aprovisionamiento de roles del DAL — idempotente.
#
# Se ejecuta automáticamente vía docker-entrypoint-initdb.d SOLO cuando el
# volumen de PostgreSQL se crea por primera vez. Sobre una base de datos ya
# existente debe aplicarse manualmente (ver docs/DAL-developer-guide.md):
#
#   docker compose exec -e DAL_APP_PASSWORD -e DAL_MIGRATOR_PASSWORD postgres \
#     sh /docker-entrypoint-initdb.d/01-roles.sh
#
# Roles:
#   vellum_migrator — DDL sobre el esquema; lo usa únicamente el contenedor
#                     efímero dal-migrate (alembic upgrade head).
#   vellum_app      — sin DDL; SELECT/INSERT/UPDATE/DELETE sobre tablas y
#                     USAGE sobre secuencias; lo usa el servicio DAL.
set -e

: "${DAL_APP_PASSWORD:?DAL_APP_PASSWORD is required}"
: "${DAL_MIGRATOR_PASSWORD:?DAL_MIGRATOR_PASSWORD is required}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_DB:=vellum}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vellum_migrator') THEN
    CREATE ROLE vellum_migrator LOGIN PASSWORD '${DAL_MIGRATOR_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vellum_app') THEN
    CREATE ROLE vellum_app LOGIN PASSWORD '${DAL_APP_PASSWORD}';
  END IF;
END
\$\$;

GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO vellum_app, vellum_migrator;

-- El migrador es quien crea objetos en el esquema; el servicio solo lo usa.
GRANT USAGE, CREATE ON SCHEMA public TO vellum_migrator;
GRANT USAGE ON SCHEMA public TO vellum_app;

-- Objetos ya existentes (re-aplicable sin efecto si ya están concedidos).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO vellum_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vellum_app;

-- Objetos futuros creados por las migraciones: accesibles para el servicio
-- sin grants manuales.
ALTER DEFAULT PRIVILEGES FOR ROLE vellum_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vellum_app;
ALTER DEFAULT PRIVILEGES FOR ROLE vellum_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO vellum_app;
EOSQL

echo "init-roles: roles vellum_app / vellum_migrator provisioned in ${POSTGRES_DB}"
