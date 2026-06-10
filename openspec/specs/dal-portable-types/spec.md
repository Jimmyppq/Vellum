# dal-portable-types

### Requirement: Tipos de columna portables entre motores

El esquema del DAL (`app/models/schema.py`) SHALL definir todas sus columnas exclusivamente con tipos SQLAlchemy portables, sin importar `sqlalchemy.dialects.*` directamente. Los campos JSON SHALL usar un tipo portable que resuelva a `JSONB` cuando el motor activo es PostgreSQL, a `CLOB` con serialización JSON en Oracle (cuyo dialecto SQLAlchemy no renderiza DDL para el tipo JSON genérico) y al tipo JSON del dialecto en cualquier otro motor. Los identificadores SHALL usar `sqlalchemy.Uuid(as_uuid=True)` (o el alias portable equivalente).

#### Scenario: DDL compilable en motores no-PostgreSQL

- **WHEN** se compila el DDL de `metadata` contra un dialecto distinto de PostgreSQL (p. ej. Oracle, SQL-Server, MySQL o SQLite)
- **THEN** la compilación se completa sin errores y los campos JSON/UUID se resuelven al tipo correspondiente del dialecto

#### Scenario: PostgreSQL conserva los tipos optimizados

- **WHEN** se compila el DDL de `metadata` contra el dialecto PostgreSQL
- **THEN** los campos JSON se emiten como `JSONB` y los identificadores como `UUID` nativo, idénticos al esquema actualmente desplegado

### Requirement: Punto único de definición de tipos portables

Los tipos portables SHALL definirse en un único módulo (`app/models/types.py`), que es el único lugar del DAL autorizado a importar de `sqlalchemy.dialects.postgresql`. El esquema y las migraciones SHALL consumir los tipos desde ese módulo.

#### Scenario: Schema sin imports de dialecto

- **WHEN** se inspecciona el código fuente de `app/models/schema.py`
- **THEN** no contiene ningún import de `sqlalchemy.dialects`

### Requirement: Migraciones sin tipos propietarios de motor

Las migraciones de Alembic SHALL usar exclusivamente tipos portables (los de `app/models/types.py` o tipos genéricos de SQLAlchemy), conforme a CLAUDE.md §7. La migración inicial existente SHALL reescribirse con tipos portables conservando su identificador de revisión.

#### Scenario: Migración inicial equivalente al esquema desplegado

- **WHEN** se aplica la migración inicial reescrita sobre una base de datos PostgreSQL limpia y se ejecuta un autogenerate de Alembic con `compare_type=True` contra `metadata`
- **THEN** el autogenerate no produce ninguna diferencia (diff vacío)

#### Scenario: La revisión no cambia

- **WHEN** una base de datos existente, migrada antes de este cambio, arranca el servicio DAL tras desplegar la versión nueva
- **THEN** la verificación del schema gate pasa sin requerir ninguna migración adicional

### Requirement: Protección anti-regresión de imports de dialecto

La suite de tests del DAL SHALL incluir un test estático que falle si `sqlalchemy.dialects` aparece importado o referenciado en `app/models/` o en `migrations/versions/`, con `app/models/types.py` como única exención.

#### Scenario: Reintroducción detectada

- **WHEN** un archivo de `app/models/` (distinto de `types.py`) o una migración añade un import de `sqlalchemy.dialects.postgresql`
- **THEN** el test anti-regresión falla identificando el archivo infractor

#### Scenario: Exención del módulo de tipos

- **WHEN** el test escanea `app/models/types.py`
- **THEN** el import de `sqlalchemy.dialects.postgresql` que encapsula está permitido y el test pasa
