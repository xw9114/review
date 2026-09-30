"""Preserve collected content when a reader confirms a supplement."""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0007"
down_revision = "20260926_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("content_origin", sa.String(16), nullable=False, server_default="collected"))
        batch.add_column(sa.Column("content_revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("collected_title", sa.String(200)))
        batch.add_column(sa.Column("collected_content", sa.Text()))
        batch.add_column(sa.Column("collected_hash", sa.String(64)))
        batch.add_column(sa.Column("supplement_base_hash", sa.String(64)))
        batch.create_check_constraint("ck_source_documents_content_origin", "content_origin IN ('collected', 'supplement')")
        batch.create_check_constraint("ck_source_documents_content_revision", "content_revision >= 1")
    op.execute("UPDATE source_documents SET collected_title=title, collected_content=content, collected_hash=content_hash")


def downgrade() -> None:
    with op.batch_alter_table("source_documents") as batch:
        batch.drop_constraint("ck_source_documents_content_revision", type_="check")
        batch.drop_constraint("ck_source_documents_content_origin", type_="check")
        for column in ("supplement_base_hash", "collected_hash", "collected_content", "collected_title", "content_revision", "content_origin"):
            batch.drop_column(column)
