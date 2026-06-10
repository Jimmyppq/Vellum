# Proposal: dal-portable-column-types

## Why

La auditoría del 31 de mayo (AUDITORIA 31-may.md) marcó como crítico bloqueante para staging que `schema.py` importa tipos propietarios de PostgreSQL (`sqlalchemy.dialects.postgresql.JSONB` y `UUID`). El hallazgo es más amplio de lo reportado: `UUID` del dialecto PostgreSQL se usa en todas las tablas, y la migración inicial de Alembic repite ambos tipos propietarios, violando la regla de CLAUDE.md §7 ("nunca usar features propietarios de un motor en migraciones"). Con esto, el DAL no puede generar DDL ni compilar queries contra Oracle, SQL-Server, MySQL o MariaDB — motores que la arquitectura exige soportar.

## What Changes

- Nuevo módulo `dal/app/models/types.py` con tipos portables:
  - `PortableJSON = JSON().with_variant(JSONB(), "postgresql")` — JSON genérico en todos los motores, `JSONB` en PostgreSQL (el DDL generado en PostgreSQL no cambia).
  - UUID mediante `sqlalchemy.Uuid(as_uuid=True)` (SQLAlchemy ≥ 2.0): `UUID` nativo en PostgreSQL/MSSQL, `CHAR(32)` en Oracle/MySQL.
- `dal/app/models/schema.py` deja de importar `sqlalchemy.dialects.postgresql` y usa los tipos portables.
- La migración inicial (`20260531_a1b2c3d4e5f6_initial_schema.py`) se reescribe con los mismos tipos portables. Es seguro porque el DDL resultante en PostgreSQL es idéntico al actual (verificado por el schema gate existente).
- Configurar `compare_type=True` en `env.py` de Alembic para que futuros autogenerate detecten divergencias de tipos.
- Test anti-regresión que falla si `sqlalchemy.dialects.postgresql` (o cualquier `sqlalchemy.dialects.*`) aparece importado en `dal/app/models/` o en nuevas migraciones.

No es un cambio breaking: el esquema desplegado en PostgreSQL permanece byte a byte igual.

## Capabilities

### New Capabilities

- `dal-portable-types`: el esquema del DAL y sus migraciones usan exclusivamente tipos SQLAlchemy portables entre motores (PostgreSQL, Oracle, SQL-Server, MySQL/MariaDB), preservando los tipos optimizados (`JSONB`, `UUID` nativo) cuando el motor activo es PostgreSQL, con protección anti-regresión automatizada.

### Modified Capabilities

(Ninguna — los requisitos de `dal-schema-migrations` no cambian; el gate existente actúa como verificación de que el DDL en PostgreSQL no varía.)

## Impact

- **Código**: `dal/app/models/schema.py`, nuevo `dal/app/models/types.py`, `dal/migrations/versions/20260531_a1b2c3d4e5f6_initial_schema.py`, `dal/migrations/env.py`.
- **Tests**: nuevo test anti-regresión de imports; el schema gate existente (`dal/tests/test_schema_gate.py`) valida que metadata y migraciones siguen alineadas.
- **Despliegues existentes (PostgreSQL)**: sin impacto — no se requiere nueva migración ni `ALTER`.
- **Dependencias**: ninguna nueva; requiere SQLAlchemy ≥ 2.0 (ya fijado en `requirements.txt` como `>=2.0.36`).
- **Futuro**: desbloquea providers `oracle.py`, `sqlserver.py`, `mysql.py` previstos en la arquitectura del DAL.
