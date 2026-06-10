"""Tipos de columna portables entre motores de base de datos.

Este módulo es el ÚNICO punto del DAL autorizado a importar de
``sqlalchemy.dialects.*`` (ver test_portable_types.py). El esquema
(schema.py) y las migraciones de Alembic deben consumir los tipos
definidos aquí, nunca tipos propietarios de un motor.

Resolución por motor:

- ``PortableJSON``: ``JSONB`` en PostgreSQL (idéntico al esquema
  desplegado, preserva operadores ``@>`` e índices GIN); ``CLOB`` con
  serialización JSON en Oracle (su dialecto SQLAlchemy no renderiza DDL
  para el tipo JSON genérico); el tipo JSON del dialecto en el resto
  (SQL-Server, MySQL/MariaDB).
- ``PortableUUID``: ``UUID`` nativo en PostgreSQL, ``UNIQUEIDENTIFIER``
  en SQL-Server, ``CHAR(32)`` (hex sin guiones) en Oracle/MySQL.
  Siempre entrega/acepta ``uuid.UUID`` en Python (``as_uuid=True``).
"""
import json

from sqlalchemy import CLOB, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator


class _JSONAsCLOB(TypeDecorator):
    """JSON serializado sobre CLOB, para motores sin tipo JSON en DDL."""

    impl = CLOB
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else json.dumps(value)

    def process_result_value(self, value, dialect):
        return None if value is None else json.loads(value)


def PortableJSON() -> JSON:
    """Tipo JSON portable: JSONB solo cuando el motor es PostgreSQL."""
    return JSON().with_variant(JSONB(), "postgresql").with_variant(_JSONAsCLOB(), "oracle")


def PortableUUID() -> Uuid:
    """Tipo UUID portable, resuelto al tipo nativo de cada motor."""
    return Uuid(as_uuid=True)
