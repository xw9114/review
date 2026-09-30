from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.knowledge_point import KnowledgePoint
    from app.models.source_document import SourceDocument
    from app.models.topic import Topic


class KnowledgeDraft(TimestampMixin, Base):
    __tablename__ = "knowledge_drafts"
    __table_args__ = (
        UniqueConstraint("source_document_id", name="uq_knowledge_drafts_source_document"),
        UniqueConstraint("knowledge_point_id", name="uq_knowledge_drafts_knowledge_point"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'stale')",
            name="ck_knowledge_drafts_status",
        ),
        CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_knowledge_drafts_difficulty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": revision}
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    key_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    quiz_items: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    knowledge_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), index=True
    )

    source_document: Mapped["SourceDocument"] = relationship(back_populates="draft")
    topic: Mapped["Topic | None"] = relationship()
    knowledge_point: Mapped["KnowledgePoint | None"] = relationship()
