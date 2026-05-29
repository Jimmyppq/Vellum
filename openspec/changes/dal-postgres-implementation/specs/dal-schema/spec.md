## ADDED Requirements

### Requirement: All tables are defined using SQLAlchemy Table objects
The system SHALL define all database tables in `dal/app/models/schema.py` using `sqlalchemy.Table` with a shared `MetaData` instance. The ORM declarative API (`declarative_base()`) SHALL NOT be used. All primary keys SHALL be UUID type, generated in Python with `uuid.uuid4()`, never delegated to the database engine.

#### Scenario: Schema module imports without ORM dependency
- **WHEN** `dal/app/models/schema.py` is imported
- **THEN** it SHALL NOT import `declarative_base` or any ORM mapper

#### Scenario: All UUIDs are Python-generated
- **WHEN** a repository inserts a new row without providing an `id`
- **THEN** the repository layer SHALL generate the UUID with `uuid.uuid4()` before executing the insert

### Requirement: Eleven tables are defined with the specified minimum fields
The system SHALL define the following tables with at minimum the fields listed:

- `users`: `id` (UUID PK), `username` (VARCHAR NOT NULL UNIQUE), `email` (VARCHAR NOT NULL UNIQUE), `is_active` (BOOLEAN NOT NULL DEFAULT TRUE), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL), `updated_at` (TIMESTAMP WITH TIME ZONE NOT NULL)
- `roles`: `id` (UUID PK), `name` (VARCHAR NOT NULL UNIQUE), `description` (TEXT)
- `user_roles`: `user_id` (UUID FK → users.id NOT NULL), `role_id` (UUID FK → roles.id NOT NULL), composite PK (`user_id`, `role_id`)
- `prompts`: `id` (UUID PK), `name` (VARCHAR NOT NULL), `description` (TEXT), `owner_id` (UUID FK → users.id NOT NULL), `status` (VARCHAR NOT NULL, values: `draft`/`approved`/`deprecated`), `visibility` (VARCHAR NOT NULL), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL), `updated_at` (TIMESTAMP WITH TIME ZONE NOT NULL)
- `prompt_versions`: `id` (UUID PK), `prompt_id` (UUID FK → prompts.id NOT NULL), `version_number` (INTEGER NOT NULL), `content` (TEXT NOT NULL), `change_log` (TEXT), `created_by` (UUID FK → users.id NOT NULL), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL), `is_active` (BOOLEAN NOT NULL DEFAULT FALSE)
- `transcripts`: `id` (UUID PK), `name` (VARCHAR NOT NULL), `media_url` (VARCHAR), `owner_id` (UUID FK → users.id NOT NULL), `status` (VARCHAR NOT NULL), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL), `updated_at` (TIMESTAMP WITH TIME ZONE NOT NULL)
- `transcript_versions`: `id` (UUID PK), `transcript_id` (UUID FK → transcripts.id NOT NULL), `version_number` (INTEGER NOT NULL), `content` (TEXT NOT NULL), `change_log` (TEXT), `created_by` (UUID FK → users.id NOT NULL), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL), `is_active` (BOOLEAN NOT NULL DEFAULT FALSE)
- `executions`: `id` (UUID PK), `prompt_id` (UUID FK → prompts.id NOT NULL), `version_id` (UUID FK → prompt_versions.id NOT NULL), `transcript_id` (UUID FK → transcripts.id NULLABLE), `executed_by` (UUID FK → users.id NOT NULL), `input_data` (JSONB NOT NULL), `output_data` (JSONB NULLABLE), `status` (VARCHAR NOT NULL, values: `queued`/`running`/`completed`/`failed`), `model_used` (VARCHAR), `cost` (NUMERIC), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL), `completed_at` (TIMESTAMP WITH TIME ZONE NULLABLE)
- `connectors`: `id` (UUID PK), `type` (VARCHAR NOT NULL), `name` (VARCHAR NOT NULL), `is_active` (BOOLEAN NOT NULL DEFAULT TRUE), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL)
- `connector_configs`: `id` (UUID PK), `connector_id` (UUID FK → connectors.id NOT NULL), `config` (JSONB NOT NULL), `encrypted` (BOOLEAN NOT NULL DEFAULT FALSE), `created_at` (TIMESTAMP WITH TIME ZONE NOT NULL)
- `system_config`: `key` (VARCHAR PK), `value` (JSONB NOT NULL), `updated_at` (TIMESTAMP WITH TIME ZONE NOT NULL)

#### Scenario: Schema creates all tables in a fresh database
- **WHEN** `metadata.create_all(engine)` is called against an empty PostgreSQL database
- **THEN** all 11 tables SHALL be created without errors

#### Scenario: executions.status accepts only valid values
- **WHEN** an insert into `executions` uses a status value outside `{queued, running, completed, failed}`
- **THEN** the database or application layer SHALL reject the insert

### Requirement: Mandatory indexes are defined
The system SHALL define the following indexes using `sqlalchemy.Index`:

- `idx_prompt_versions_prompt_id_version_number` on `prompt_versions(prompt_id, version_number)`
- `idx_executions_prompt_id` on `executions(prompt_id)`
- `idx_executions_status` on `executions(status)`
- `idx_executions_created_at` on `executions(created_at)`
- `idx_prompts_status` on `prompts(status)`
- `idx_prompts_owner_id` on `prompts(owner_id)`

#### Scenario: Indexes exist after schema creation
- **WHEN** the schema is applied to PostgreSQL
- **THEN** querying `pg_indexes` SHALL return all six named indexes

### Requirement: prompt_versions and transcript_versions are immutable
The system SHALL enforce that `content` fields in `prompt_versions` and `transcript_versions` are never updated after creation. New content requires inserting a new version row, not modifying an existing one.

#### Scenario: Repository rejects UPDATE on version content
- **WHEN** a caller attempts to update the `content` field of an existing version row
- **THEN** the repository SHALL raise a `NotImplementedError` or return an error response — no UPDATE query SHALL be issued
