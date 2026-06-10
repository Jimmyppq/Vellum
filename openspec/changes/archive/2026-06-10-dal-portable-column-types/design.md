# Design: dal-portable-column-types

## Context

`dal/app/models/schema.py` importa `JSONB` y `UUID` de `sqlalchemy.dialects.postgresql` (línea 14) y los usa en todas las tablas: `UUID` en todas las PK/FK y `JSONB` en `executions.input_data/output_data`, `connector_configs.config` y `system_config.value`. La migración inicial (`20260531_a1b2c3d4e5f6_initial_schema.py`) repite ambos tipos. Esto hace imposible compilar DDL/queries contra Oracle, SQL-Server, MySQL o MariaDB, motores que CLAUDE.md exige soportar, y viola la regla §7 sobre tipos propietarios en migraciones.

Estado relevante:
- SQLAlchemy fijado en `>=2.0.36`, por lo que `sqlalchemy.Uuid` y `with_variant` están disponibles.
- `migrations/env.py` ya configura `compare_type=True` en online y offline (solo hay que verificarlo, no cambiarlo).
- Existe un schema gate (`dal-schema-migrations`, recién archivado) que verifica en arranque que `alembic_version` está en head. Compara revisión, **no** estructura DDL — no sirve por sí solo para demostrar que el DDL no cambió.

## Goals / Non-Goals

**Goals:**
- Eliminar todo import de `sqlalchemy.dialects.*` de `app/models/` y de la migración inicial.
- DDL generado en PostgreSQL idéntico al actual (mismo `JSONB`, mismo `UUID` nativo): cero impacto en despliegues existentes, sin nueva migración.
- Protección anti-regresión automatizada contra reintroducción de tipos propietarios.

**Non-Goals:**
- Implementar los providers `oracle.py`, `sqlserver.py`, `mysql.py` (este cambio solo los desbloquea).
- CI contra motores distintos de PostgreSQL.
- Cambiar el comportamiento del schema gate o del flujo de migraciones.

## Decisions

### D1: `with_variant` en lugar de tipo genérico puro o `TypeDecorator`

`PortableJSON = JSON().with_variant(JSONB(), "postgresql")` en un nuevo módulo `dal/app/models/types.py`.

- *Alternativa A (solo `sa.JSON`)*: descartada — en PostgreSQL generaría `JSON` en lugar de `JSONB`, divergiendo del esquema desplegado y forzando un `ALTER` en todas las instalaciones.
- *Alternativa C (`TypeDecorator` custom)*: descartada — complejidad especulativa; el JSON genérico de SQLAlchemy ya resuelve correctamente en Oracle/MSSQL/MySQL.

Nota: `types.py` sí importa `JSONB` de `sqlalchemy.dialects.postgresql` — es el único punto permitido, encapsulado tras el tipo portable. El test anti-regresión lo exime explícitamente.

**Ajuste durante implementación (2026-06-10):** el dialecto Oracle de SQLAlchemy no renderiza DDL para el tipo `JSON` genérico (`CompileError` verificado en la suite). `PortableJSON` añade una segunda variante para Oracle: `_JSONAsCLOB` (`TypeDecorator` sobre `CLOB` con serialización `json.dumps/loads`). Es el uso acotado de `TypeDecorator` que la alternativa C descartaba como solución general — aquí se limita al caso que el tipo genérico no cubre, tal como preveía la sección de riesgos.

### D2: UUID mediante `sqlalchemy.Uuid(as_uuid=True)`

SQLAlchemy 2.0 lo resuelve por dialecto: `UUID` nativo en PostgreSQL, `UNIQUEIDENTIFIER` en MSSQL, `CHAR(32)` en Oracle/MySQL. Se expone como `PortableUUID` en `types.py` (alias o función fábrica) para que `schema.py` y las migraciones tengan un único punto de import. No se usa `sqlalchemy.UUID` (subclase también válida) para mantener la semántica `as_uuid=True` explícita en un solo sitio.

### D3: Reescribir la migración inicial in-place, sin nueva migración

La migración ya está aplicada en entornos existentes. Reescribirla es seguro porque el DDL emitido en PostgreSQL no cambia (D1/D2) y la revisión (`a1b2c3d4e5f6`) se conserva, así que el gate de arranque no se ve afectado. Crear una migración nueva no aportaría nada: no hay cambio estructural que aplicar.

### D4: Verificación de equivalencia DDL mediante autogenerate vacío

El gate existente no compara estructura, así que la prueba de "DDL idéntico" es: contra una BD migrada con la migración reescrita, un autogenerate de Alembic (`alembic check` o equivalente programático) no debe producir diferencias frente a `metadata`. Esto valida a la vez schema.py ↔ migración y la equivalencia con el esquema desplegado. Se añade como test (o se verifica manualmente en la implementación si ya existe un test equivalente en la suite).

### D5: Test anti-regresión de imports

Test que escanea `dal/app/models/` y `dal/migrations/versions/` y falla si encuentra `sqlalchemy.dialects` (import o uso), con `app/models/types.py` como única exención. Análisis estático por AST o grep sobre el código fuente; no requiere BD. Mismo espíritu que el schema gate: la regla arquitectónica se hace ejecutable.

## Risks / Trade-offs

- [El DDL con `with_variant` difiere sutilmente del actual — p. ej. `JSONB(astext_type=Text())`] → Mitigación: D4 (autogenerate vacío con `compare_type=True`) lo detecta antes de merge; el cambio no se da por bueno hasta que el diff sea vacío.
- [Queries existentes en el provider postgres que dependan de operadores JSONB (`@>`, GIN)] → Con `with_variant` el tipo en PostgreSQL sigue siendo JSONB, así que no se rompen; pero si existieran, son deuda de portabilidad a inventariar (fuera de alcance, anotar si aparecen).
- [`Uuid(as_uuid=True)` en motores sin UUID nativo almacena CHAR(32) sin guiones] → Irrelevante hoy (solo PostgreSQL desplegado); decisión consciente para el futuro, documentada en `types.py`.
- [Reescribir una migración aplicada es, en general, mala práctica] → Aceptado deliberadamente porque la equivalencia DDL está garantizada por D4 y la alternativa (migración nueva no-op) ensucia el historial sin beneficio.

## Migration Plan

1. Añadir `types.py` + actualizar `schema.py` y la migración inicial en el mismo commit.
2. Ejecutar suite completa del DAL (incluye schema gate) + verificación D4 contra BD limpia migrada.
3. Despliegue: ninguno necesario — no hay cambio de esquema; los entornos existentes no se tocan.
4. Rollback: revertir el commit; no hay estado de BD que deshacer.

## Open Questions

Ninguna pendiente.

- ~~¿Conviene extender el test anti-regresión a todo `dal/app/` (no solo `models/`)?~~ **Resuelto (2026-06-10):** el alcance del test anti-regresión es `app/models/` + `migrations/versions/`; se ampliará cuando exista un segundo provider.
