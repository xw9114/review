"""Add source documents and knowledge point provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0002"
down_revision: str | None = "20260922_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'ignored', 'stale')",
            name="ck_source_documents_status",
        ),
        sa.UniqueConstraint(
            "provider", "external_id", name="uq_source_documents_provider_external"
        ),
    )
    op.create_index("ix_source_documents_provider", "source_documents", ["provider"])
    op.create_index("ix_source_documents_content_hash", "source_documents", ["content_hash"])
    op.create_index("ix_source_documents_status", "source_documents", ["status"])

    op.create_table(
        "knowledge_point_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "source_document_id", name="uq_knowledge_point_sources_document"
        ),
        sa.UniqueConstraint(
            "knowledge_point_id",
            "source_document_id",
            name="uq_knowledge_point_sources_pair",
        ),
    )
    op.create_index(
        "ix_knowledge_point_sources_knowledge_point_id",
        "knowledge_point_sources",
        ["knowledge_point_id"],
    )
    op.create_index(
        "ix_knowledge_point_sources_source_document_id",
        "knowledge_point_sources",
        ["source_document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_point_sources_source_document_id", table_name="knowledge_point_sources"
    )
    op.drop_index(
        "ix_knowledge_point_sources_knowledge_point_id", table_name="knowledge_point_sources"
    )
    op.drop_table("knowledge_point_sources")
    op.drop_index("ix_source_documents_status", table_name="source_documents")
    op.drop_index("ix_source_documents_content_hash", table_name="source_documents")
    op.drop_index("ix_source_documents_provider", table_name="source_documents")
    op.drop_table("source_documents")
