"""Add AI knowledge drafts and structured knowledge fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0005"
down_revision: str | None = "20260924_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_points") as batch:
        batch.add_column(sa.Column("summary", sa.Text()))
        batch.add_column(sa.Column("difficulty", sa.String(length=16)))
        batch.add_column(sa.Column("key_points", sa.JSON()))
        batch.add_column(sa.Column("quiz_items", sa.JSON()))
        batch.create_check_constraint(
            "ck_knowledge_points_difficulty",
            "difficulty IS NULL OR difficulty IN ('beginner', 'intermediate', 'advanced')",
        )

    op.create_table(
        "knowledge_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("topics.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("key_points", sa.JSON(), nullable=False),
        sa.Column("quiz_items", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("generation_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "knowledge_point_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_document_id", name="uq_knowledge_drafts_source_document"
        ),
        sa.UniqueConstraint(
            "knowledge_point_id", name="uq_knowledge_drafts_knowledge_point"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'stale')",
            name="ck_knowledge_drafts_status",
        ),
        sa.CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_knowledge_drafts_difficulty",
        ),
    )
    op.create_index("ix_knowledge_drafts_source_document_id", "knowledge_drafts", ["source_document_id"])
    op.create_index("ix_knowledge_drafts_topic_id", "knowledge_drafts", ["topic_id"])
    op.create_index("ix_knowledge_drafts_status", "knowledge_drafts", ["status"])
    op.create_index("ix_knowledge_drafts_knowledge_point_id", "knowledge_drafts", ["knowledge_point_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_drafts_knowledge_point_id", table_name="knowledge_drafts")
    op.drop_index("ix_knowledge_drafts_status", table_name="knowledge_drafts")
    op.drop_index("ix_knowledge_drafts_topic_id", table_name="knowledge_drafts")
    op.drop_index("ix_knowledge_drafts_source_document_id", table_name="knowledge_drafts")
    op.drop_table("knowledge_drafts")

    with op.batch_alter_table("knowledge_points") as batch:
        batch.drop_constraint("ck_knowledge_points_difficulty", type_="check")
        batch.drop_column("quiz_items")
        batch.drop_column("key_points")
        batch.drop_column("difficulty")
        batch.drop_column("summary")
