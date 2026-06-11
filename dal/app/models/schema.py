from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)
from app.models.types import PortableJSON, PortableUUID

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("username", String(255), nullable=False, unique=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

roles = Table(
    "roles",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("description", Text),
)

user_roles = Table(
    "user_roles",
    metadata,
    Column("user_id", PortableUUID(), ForeignKey("users.id"), nullable=False, primary_key=True),
    Column("role_id", PortableUUID(), ForeignKey("roles.id"), nullable=False, primary_key=True),
)

prompts = Table(
    "prompts",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("description", Text),
    Column("owner_id", PortableUUID(), ForeignKey("users.id"), nullable=False),
    Column("status", String(50), nullable=False, default="draft"),
    Column("visibility", String(50), nullable=False, default="private"),
    Column("is_deleted", Boolean, nullable=False, default=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

prompt_versions = Table(
    "prompt_versions",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("prompt_id", PortableUUID(), ForeignKey("prompts.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("content", Text, nullable=False),
    Column("change_log", Text),
    Column("created_by", PortableUUID(), ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("is_active", Boolean, nullable=False, default=False),
)

transcripts = Table(
    "transcripts",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("media_url", String(1024)),
    Column("owner_id", PortableUUID(), ForeignKey("users.id"), nullable=False),
    Column("status", String(50), nullable=False),
    Column("is_deleted", Boolean, nullable=False, default=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

transcript_versions = Table(
    "transcript_versions",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("transcript_id", PortableUUID(), ForeignKey("transcripts.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("content", Text, nullable=False),
    Column("change_log", Text),
    Column("created_by", PortableUUID(), ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("is_active", Boolean, nullable=False, default=False),
)

executions = Table(
    "executions",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("prompt_id", PortableUUID(), ForeignKey("prompts.id"), nullable=False),
    Column("version_id", PortableUUID(), ForeignKey("prompt_versions.id"), nullable=False),
    Column("transcript_id", PortableUUID(), ForeignKey("transcripts.id"), nullable=True),
    Column("executed_by", PortableUUID(), ForeignKey("users.id"), nullable=False),
    Column("input_data", PortableJSON(), nullable=False),
    Column("output_data", PortableJSON(), nullable=True),
    Column("status", String(50), nullable=False, default="queued"),
    Column("model_used", String(255)),
    Column("cost", Numeric(10, 6)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)

connectors = Table(
    "connectors",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("type", String(100), nullable=False),
    Column("name", String(255), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

connector_configs = Table(
    "connector_configs",
    metadata,
    Column("id", PortableUUID(), primary_key=True),
    Column("connector_id", PortableUUID(), ForeignKey("connectors.id"), nullable=False),
    Column("config", PortableJSON(), nullable=False),
    Column("encrypted", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

system_config = Table(
    "system_config",
    metadata,
    Column("key", String(255), primary_key=True),
    Column("value", PortableJSON(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# Mandatory indexes
Index("idx_prompt_versions_prompt_id_version_number", prompt_versions.c.prompt_id, prompt_versions.c.version_number)
Index("idx_executions_prompt_id", executions.c.prompt_id)
Index("idx_executions_status", executions.c.status)
Index("idx_executions_created_at", executions.c.created_at)
Index("idx_prompts_status", prompts.c.status)
Index("idx_prompts_owner_id", prompts.c.owner_id)
