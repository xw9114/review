"""Add deterministic weak-point counters plus error-analysis and question-variant tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260930_0008"
down_revision = "20260926_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_progress", sa.Column("again_streak", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("review_progress", sa.Column("total_again", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("review_progress", sa.Column("total_hard", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "error_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("error_type", sa.String(24), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "error_type IN ('concept_confusion', 'incomplete_recall', 'terminology_mixup', 'slip', 'other')",
            name="ck_error_analyses_error_type",
        ),
    )

    op.create_table(
        "question_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_question_variants_status"),
    )
    op.create_index(
        "ix_question_variants_point_status", "question_variants", ["knowledge_point_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_question_variants_point_status", table_name="question_variants")
    op.drop_table("question_variants")
    op.drop_table("error_analyses")
    with op.batch_alter_table("review_progress") as batch:
        batch.drop_column("total_hard")
        batch.drop_column("total_again")
        batch.drop_column("again_streak")
