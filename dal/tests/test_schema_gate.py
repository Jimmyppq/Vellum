"""Tests del gate de migraciones: verify_schema_version, lifespan y permisos.

Estos tests usan la misma BD de test que el resto de la suite. La tabla
alembic_version se crea/elimina por test para simular cada estado del esquema;
las tablas del modelo (creadas por el fixture de sesión) no se tocan.
"""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import _expected_head, verify_schema_version
from tests.conftest import TEST_DATABASE_URL


def _make_engine(url=TEST_DATABASE_URL):
    return create_async_engine(url, poolclass=NullPool)


async def _stamp(engine, revision: str | None) -> None:
    """Deja alembic_version en el estado pedido (None = sin tabla)."""
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        if revision is not None:
            await conn.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            )
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                {"rev": revision},
            )


@pytest.fixture
async def gate_engine():
    engine = _make_engine()
    yield engine
    await _stamp(engine, None)  # limpiar: la suite no espera alembic_version
    await engine.dispose()


async def test_verify_passes_when_schema_at_head(gate_engine):
    await _stamp(gate_engine, _expected_head())
    await verify_schema_version(engine=gate_engine)  # no debe lanzar


async def test_verify_fails_when_not_migrated(gate_engine):
    await _stamp(gate_engine, None)
    with pytest.raises(RuntimeError, match="not migrated.*dal-migrate"):
        await verify_schema_version(engine=gate_engine)


async def test_verify_fails_when_schema_stale(gate_engine):
    await _stamp(gate_engine, "deadbeef0000")
    head = _expected_head()
    with pytest.raises(RuntimeError) as exc_info:
        await verify_schema_version(engine=gate_engine)
    msg = str(exc_info.value)
    assert "deadbeef0000" in msg
    assert head in msg


async def test_verify_connection_error_is_distinguishable():
    engine = _make_engine("postgresql+asyncpg://user:supersecretpw@127.0.0.1:1/nodb")
    try:
        with pytest.raises(RuntimeError) as exc_info:
            await verify_schema_version(engine=engine)
    finally:
        await engine.dispose()
    msg = str(exc_info.value)
    assert "unreachable" in msg
    assert "not migrated" not in msg
    assert "supersecretpw" not in msg


@pytest.fixture
async def fresh_global_engine():
    """El _engine global del DAL agrupa conexiones ligadas al event loop que
    las creó; cada test corre en su propio loop, así que se descarta el pool
    (sin cerrar conexiones de otros loops) antes y después."""
    from app.database import _engine

    await _engine.dispose(close=False)
    yield
    await _engine.dispose(close=False)


async def test_lifespan_aborts_when_not_migrated(gate_engine, fresh_global_engine):
    from main import app, lifespan

    await _stamp(gate_engine, None)
    with pytest.raises(RuntimeError, match="not migrated"):
        async with lifespan(app):
            pass


async def test_lifespan_starts_when_schema_at_head(gate_engine, fresh_global_engine):
    from main import app, lifespan

    await _stamp(gate_engine, _expected_head())
    async with lifespan(app):
        pass


def test_lifespan_has_no_env_branch_and_no_ddl():
    """El gate aplica en todos los entornos y el servicio no contiene DDL:
    el lifespan no bifurca por ENV ni invoca create_all."""
    import inspect

    import main

    source = inspect.getsource(main.lifespan)
    assert "ENV" not in source
    assert "create_all" not in source
    import app.database as database

    assert not hasattr(database, "init_db")


# ---------------------------------------------------------------------------
# Permisos: el rol del servicio no puede ejecutar DDL
# ---------------------------------------------------------------------------

def _app_role_url():
    password = os.getenv("DAL_APP_PASSWORD", "changeme_app")
    # Misma BD de test, credenciales del rol de aplicación.
    # Se retorna el objeto URL: str(URL) enmascara el password.
    from sqlalchemy.engine import make_url

    return make_url(TEST_DATABASE_URL).set(username="vellum_app", password=password)


async def test_app_role_cannot_run_ddl():
    engine = _make_engine(_app_role_url())
    try:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            pytest.skip(
                "rol vellum_app no disponible en esta BD de test "
                "(aplicar infra/postgres/init-roles.sh)"
            )

        for ddl in (
            "CREATE TABLE ddl_denied_check (id INT)",
            "ALTER TABLE prompts ADD COLUMN ddl_denied_check INT",
            "DROP TABLE prompts",
        ):
            async with engine.connect() as conn:
                with pytest.raises(Exception, match="(?i)permission denied|must be owner"):
                    await conn.execute(text(ddl))
    finally:
        await engine.dispose()
