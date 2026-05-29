## ADDED Requirements

### Requirement: PostgresProvider builds DSN exclusively from environment variables
The system SHALL implement `PostgresProvider` in `dal/app/providers/postgres.py`. The DSN SHALL be constructed exclusively from the environment variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`. No default values for credentials SHALL be hardcoded; only port (5432) and pool parameters may have defaults.

#### Scenario: Missing required env var raises error on startup
- **WHEN** any of `DB_HOST`, `DB_NAME`, `DB_USER`, or `DB_PASSWORD` is absent from the environment
- **THEN** `PostgresProvider` initialization SHALL raise a `ValueError` or `pydantic.ValidationError` before any connection attempt

#### Scenario: DSN never appears in logs
- **WHEN** `PostgresProvider` logs connection events
- **THEN** the log entries SHALL contain only `host:port/dbname` — never the password or full DSN string

### Requirement: PostgresProvider creates an async SQLAlchemy engine with configurable pool
The system SHALL use `sqlalchemy.ext.asyncio.create_async_engine` with the `asyncpg` driver. Pool parameters `pool_size`, `max_overflow`, and `pool_timeout` SHALL be sourced from `DB_POOL_SIZE` (default 10), `DB_MAX_OVERFLOW` (default 20), and `DB_POOL_TIMEOUT` (default 30) respectively.

#### Scenario: Pool parameters are applied from environment
- **WHEN** `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10` are set
- **THEN** the engine pool SHALL reflect those values

### Requirement: health_check returns True when database is reachable
The system SHALL implement `health_check()` as an async-safe method that executes a trivial query (`SELECT 1`) and returns `True` on success, `False` on any exception, without propagating the exception to the caller.

#### Scenario: Healthy database returns True
- **WHEN** the PostgreSQL instance is reachable and accepting connections
- **THEN** `health_check()` SHALL return `True`

#### Scenario: Unreachable database returns False
- **WHEN** the PostgreSQL instance is unreachable or refuses connections
- **THEN** `health_check()` SHALL return `False` and SHALL NOT raise an exception
