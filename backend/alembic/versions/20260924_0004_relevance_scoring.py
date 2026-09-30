"""Add embeddings and relevance scoring metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0004"
down_revision: str | None = "20260923_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("topics") as batch:
        batch.add_column(sa.Column("embedding", sa.JSON()))
        batch.add_column(sa.Column("embedding_model", sa.String(length=120)))
        batch.add_column(sa.Column("embedding_input_hash", sa.String(length=64)))

    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("embedding", sa.JSON()))
        batch.add_column(sa.Column("embedding_model", sa.String(length=120)))
        batch.add_column(sa.Column("embedding_input_hash", sa.String(length=64)))
        batch.add_column(sa.Column("relevance_score", sa.Float()))
        batch.add_column(sa.Column("relevance_passed", sa.Boolean()))
        batch.add_column(sa.Column("suggested_topic_id", sa.Integer()))
        batch.add_column(sa.Column("relevance_method", sa.String(length=16)))
        batch.add_column(sa.Column("relevance_reason", sa.Text()))
        batch.add_column(
            sa.Column(
                "processing_status",
                sa.String(length=16),
                nullable=False,
                server_default="unscored",
            )
        )
        batch.add_column(sa.Column("processed_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key(
            "fk_source_documents_suggested_topic_id",
            "topics",
            ["suggested_topic_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_source_documents_suggested_topic_id", ["suggested_topic_id"]
        )
        batch.create_index("ix_source_documents_processing_status", ["processing_status"])
        batch.create_check_constraint(
            "ck_source_documents_processing_status",
            "processing_status IN ('unscored', 'scored', 'failed')",
        )
        batch.create_check_constraint(
            "ck_source_documents_relevance_method",
            "relevance_method IS NULL OR relevance_method IN ('embedding', 'keyword')",
        )
        batch.create_check_constraint(
            "ck_source_documents_relevance_score",
            "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)",
        )


def downgrade() -> None:
    with op.batch_alter_table("source_documents") as batch:
        batch.drop_constraint("ck_source_documents_relevance_score", type_="check")
        batch.drop_constraint("ck_source_documents_relevance_method", type_="check")
        batch.drop_constraint("ck_source_documents_processing_status", type_="check")
        batch.drop_index("ix_source_documents_processing_status")
        batch.drop_index("ix_source_documents_suggested_topic_id")
        batch.drop_constraint(
            "fk_source_documents_suggested_topic_id", type_="foreignkey"
        )
        batch.drop_column("processed_at")
        batch.drop_column("processing_status")
        batch.drop_column("relevance_reason")
        batch.drop_column("relevance_method")
        batch.drop_column("suggested_topic_id")
        batch.drop_column("relevance_passed")
        batch.drop_column("relevance_score")
        batch.drop_column("embedding_input_hash")
        batch.drop_column("embedding_model")
        batch.drop_column("embedding")

    with op.batch_alter_table("topics") as batch:
        batch.drop_column("embedding_input_hash")
        batch.drop_column("embedding_model")
        batch.drop_column("embedding")
