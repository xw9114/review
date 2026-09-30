"""Persist review sessions, question snapshots, schedules and draft revisions."""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0006"
down_revision = "20260924_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_drafts", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "review_progress",
        sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("quiz_hash", sa.String(64), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 5", name="ck_review_progress_level"),
    )
    op.create_index("ix_review_progress_due_at", "review_progress", ["due_at"])
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_key", sa.String(20), unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'completed')", name="ck_review_sessions_status"),
    )
    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("point_name", sa.String(160), nullable=False),
        sa.Column("topic_name", sa.String(120), nullable=False),
        sa.Column("quiz_hash", sa.String(64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("standard_answer", sa.Text(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("revealed_at", sa.DateTime(timezone=True)),
        sa.Column("rating", sa.String(10)),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_id", "position", name="uq_review_items_position"),
        sa.CheckConstraint("rating IS NULL OR rating IN ('again', 'hard', 'good', 'easy')", name="ck_review_items_rating"),
    )
    op.create_index("ix_review_items_session_id", "review_items", ["session_id"])
    op.create_index("ix_review_items_knowledge_point_id", "review_items", ["knowledge_point_id"])


def downgrade() -> None:
    op.drop_table("review_items")
    op.drop_table("review_sessions")
    op.drop_table("review_progress")
    with op.batch_alter_table("knowledge_drafts") as batch:
        batch.drop_column("revision")
