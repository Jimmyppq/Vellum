"""Tests de tipos portables: anti-regresión de imports, DDL multi-dialecto
y equivalencia entre la migración inicial y metadata.

Ver openspec/specs (dal-portable-types): app/models/types.py es el único
módulo autorizado a importar de sqlalchemy.dialects.
"""
import ast
import os
import subprocess
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateTable

from app.models.schema import connector_configs, executions, metadata, system_config, users
from tests.conftest import TEST_DATABASE_URL

DAL_DIR = Path(__file__).resolve().parents[1]

# --- 1. Anti-regresión: sin imports de sqlalchemy.dialects ---

SCAN_DIRS = ["app/models", "migrations/versions"]
EXEMPT = {DAL_DIR / "app" / "models" / "types.py"}


def _dialect_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.startswith("sqlalchemy.dialects")]
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("sqlalchemy.dialects"):
                hits.append(node.module)
            elif node.module == "sqlalchemy" and any(a.name == "dialects" for a in node.names):
                hits.append("sqlalchemy.dialects")
    return hits


def test_no_dialect_imports_outside_types_module():
    offenders = {}
    for rel in SCAN_DIRS:
        for path in (DAL_DIR / rel).rglob("*.py"):
            if path in EXEMPT:
                continue
            hits = _dialect_imports(path)
            if hits:
                offenders[str(path.relative_to(DAL_DIR))] = hits
    assert not offenders, f"Imports de sqlalchemy.dialects fuera de types.py: {offenders}"


def test_types_module_exemption_is_real():
    # La exención existe porque types.py encapsula JSONB; si deja de hacerlo,
    # este test recuerda retirar la exención.
    assert _dialect_imports(DAL_DIR / "app" / "models" / "types.py") == ["sqlalchemy.dialects.postgresql"]


# --- 2. DDL compilable en todos los dialectos ---

DIALECTS = ["postgresql", "oracle", "mssql", "mysql", "sqlite"]


@pytest.mark.parametrize("dialect_name", DIALECTS)
def test_ddl_compiles_on_all_dialects(dialect_name):
    from sqlalchemy.engine import create_mock_engine

    statements = []
    mock = create_mock_engine(f"{dialect_name}://", lambda sql, *a, **k: statements.append(str(sql.compile(dialect=mock.dialect))))
    for table in metadata.sorted_tables:
        mock.execute(CreateTable(table))
    assert len(statements) == len(metadata.sorted_tables)


def test_postgresql_emits_jsonb_and_native_uuid():
    from sqlalchemy.dialects import postgresql

    pg = postgresql.dialect()
    users_ddl = str(CreateTable(users).compile(dialect=pg))
    assert "id UUID NOT NULL" in users_ddl

    for table, json_cols in [
        (executions, ["input_data", "output_data"]),
        (connector_configs, ["config"]),
        (system_config, ["value"]),
    ]:
        ddl = str(CreateTable(table).compile(dialect=pg))
        for col in json_cols:
            assert f"{col} JSONB" in ddl, f"{table.name}.{col} no emite JSONB:\n{ddl}"


def test_oracle_does_not_emit_postgres_types():
    from sqlalchemy.dialects import oracle

    ddl = str(CreateTable(executions).compile(dialect=oracle.dialect()))
    assert "JSONB" not in ddl
    assert "UUID" not in ddl  # Oracle almacena CHAR(32)
    assert "input_data CLOB" in ddl  # JSON serializado a CLOB en Oracle


# --- 3. La migración inicial produce exactamente el esquema de metadata ---

CHECK_DB = "vellum_migration_check"


async def _recreate_check_db() -> str:
    admin = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {CHECK_DB}"))
        await conn.execute(text(f"CREATE DATABASE {CHECK_DB}"))
    await admin.dispose()
    return TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{CHECK_DB}"


async def test_initial_migration_matches_metadata():
    check_url = await _recreate_check_db()

    # Aplicar migraciones sobre la BD limpia con el env.py real (subproceso
    # para evitar el cache de get_settings y el logging config de alembic).
    env = {**os.environ, "DB_NAME": CHECK_DB}
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=DAL_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"alembic upgrade falló:\n{result.stdout}\n{result.stderr}"

    engine = create_async_engine(check_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            def _diff(sync_conn):
                ctx = MigrationContext.configure(sync_conn, opts={"compare_type": True})
                return compare_metadata(ctx, metadata)

            diffs = await conn.run_sync(_diff)
    finally:
        await engine.dispose()

    diffs = [
        d for d in diffs
        if not (d[0] == "remove_table" and getattr(d[1], "name", "") == "alembic_version")
    ]
    assert diffs == [], f"La migración no es equivalente a metadata: {diffs}"
