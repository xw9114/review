from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.knowledge_point import KnowledgePoint


class ErrorAnalysis(Base):
    """One current LLM-assisted diagnosis per knowledge point, generated on explicit request."""

    __tablename__ = "error_analyses"
    __table_args__ = (
        CheckConstraint(
            "error_type IN ('concept_confusion', 'incomplete_recall', 'terminology_mixup', 'slip', 'other')",
            name="ck_error_analyses_error_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    error_type: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    input_snapshot: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    knowledge_point: Mapped["KnowledgePoint"] = relationship()


class QuestionVariant(Base):
    """A candidate alternate-phrasing question awaiting manual approval before it joins quiz_items."""

    __tablename__ = "question_variants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_question_variants_status"
        ),
        Index("ix_question_variants_point_status", "knowledge_point_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    knowledge_point: Mapped["KnowledgePoint"] = relationship()
