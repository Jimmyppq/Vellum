# Tasks: dal-portable-column-types

## 1. Tipos portables

- [x] 1.1 Crear `dal/app/models/types.py` con `PortableJSON = JSON().with_variant(JSONB(), "postgresql")` y `PortableUUID` (fábrica/alias de `sqlalchemy.Uuid(as_uuid=True)`), con docstring que documente la resolución por motor y por qué este módulo es la única exención de imports de dialecto
- [x] 1.2 Actualizar `dal/app/models/schema.py`: eliminar el import de `sqlalchemy.dialects.postgresql` y sustituir todos los usos de `UUID(as_uuid=True)` y `JSONB` por los tipos portables

## 2. Migración inicial

- [x] 2.1 Reescribir `dal/migrations/versions/20260531_a1b2c3d4e5f6_initial_schema.py` con los tipos portables, conservando el identificador de revisión `a1b2c3d4e5f6` y el resto del DDL intacto
- [x] 2.2 Verificar que `migrations/env.py` mantiene `compare_type=True` en modo online y offline (ya presente; solo confirmar)

## 3. Verificación de equivalencia DDL

- [x] 3.1 Contra una BD PostgreSQL limpia migrada con la migración reescrita, ejecutar autogenerate de Alembic (`alembic check` o equivalente programático) y confirmar diff vacío frente a `metadata`
- [x] 3.2 Añadir test de compilación de DDL multi-dialecto: compilar `metadata` con `CreateTable` contra los dialectos postgresql, oracle, mssql y mysql sin errores, y asertar que en PostgreSQL los campos JSON emiten `JSONB` y los ids `UUID`

## 4. Anti-regresión

- [x] 4.1 Crear test estático (AST o escaneo de fuente, sin BD) que falle si `sqlalchemy.dialects` aparece en `dal/app/models/` (exención: `types.py`) o en `dal/migrations/versions/`, reportando el archivo infractor

## 5. Validación final

- [x] 5.1 Ejecutar la suite completa del DAL (incluido `test_schema_gate.py`) y confirmar que todo pasa
- [x] 5.2 Actualizar `docs/DAL-developer-guide.md`: la sección que decía que los campos JSONB eran "el único punto de adaptación" al migrar de motor debe reflejar los nuevos tipos portables y la regla de imports
