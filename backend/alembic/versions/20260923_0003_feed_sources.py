"""Add feed sources and source metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0003"
down_revision: str | None = "20260923_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feed_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("cleaning_mode", sa.String(length=16), nullable=False, server_default="auto"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sa.String(length=16), nullable=False, server_default="never"),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_cleaned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_type IN ('rss', 'rsshub')", name="ck_feed_sources_type"),
        sa.CheckConstraint(
            "cleaning_mode IN ('feed', 'auto', 'crawl4ai')",
            name="ck_feed_sources_cleaning_mode",
        ),
        sa.CheckConstraint(
            "last_sync_status IN ('never', 'success', 'partial', 'failed')",
            name="ck_feed_sources_sync_status",
        ),
        sa.UniqueConstraint("name", name="uq_feed_sources_name"),
    )
    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("feed_source_id", sa.Integer()))
        batch.add_column(sa.Column("source_url", sa.Text()))
        batch.add_column(sa.Column("author", sa.String(length=200)))
        batch.create_foreign_key(
            "fk_source_documents_feed_source_id",
            "feed_sources",
            ["feed_source_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_source_documents_feed_source_id", ["feed_source_id"])


def downgrade() -> None:
    with op.batch_alter_table("source_documents") as batch:
        batch.drop_index("ix_source_documents_feed_source_id")
        batch.drop_constraint("fk_source_documents_feed_source_id", type_="foreignkey")
        batch.drop_column("author")
        batch.drop_column("source_url")
        batch.drop_column("feed_source_id")
    op.drop_table("feed_sources")
