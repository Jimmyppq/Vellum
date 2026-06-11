"""soft delete columns on prompts and transcripts

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills existing rows; the application sets the value
    # explicitly on every insert, so the default never masks a missing write
    op.add_column(
        "prompts",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("prompts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "transcripts",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("transcripts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("transcripts", "deleted_at")
    op.drop_column("transcripts", "is_deleted")
    op.drop_column("prompts", "deleted_at")
    op.drop_column("prompts", "is_deleted")
