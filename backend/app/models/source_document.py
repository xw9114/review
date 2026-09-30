from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.feed_source import FeedSource
    from app.models.knowledge_point_source import KnowledgePointSource
    from app.models.knowledge_draft import KnowledgeDraft
    from app.models.topic import Topic


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_source_documents_provider_external"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'ignored', 'stale')",
            name="ck_source_documents_status",
        ),
        CheckConstraint(
            "processing_status IN ('unscored', 'scored', 'failed')",
            name="ck_source_documents_processing_status",
        ),
        CheckConstraint(
            "relevance_method IS NULL OR relevance_method IN ('embedding', 'keyword')",
            name="ck_source_documents_relevance_method",
        ),
        CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)",
            name="ck_source_documents_relevance_score",
        ),
        CheckConstraint("content_origin IN ('collected', 'supplement')", name="ck_source_documents_content_origin"),
        CheckConstraint("content_revision >= 1", name="ck_source_documents_content_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    feed_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("feed_sources.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="collected", server_default="collected")
    content_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    collected_title: Mapped[str | None] = mapped_column(String(200))
    collected_content: Mapped[str | None] = mapped_column(Text)
    collected_hash: Mapped[str | None] = mapped_column(String(64))
    supplement_base_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(200))
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_input_hash: Mapped[str | None] = mapped_column(String(64))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    relevance_passed: Mapped[bool | None] = mapped_column(Boolean)
    suggested_topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )
    relevance_method: Mapped[str | None] = mapped_column(String(16))
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unscored", index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    feed_source: Mapped["FeedSource | None"] = relationship(back_populates="documents")
    suggested_topic: Mapped["Topic | None"] = relationship(foreign_keys=[suggested_topic_id])
    draft: Mapped["KnowledgeDraft | None"] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    knowledge_links: Mapped[list["KnowledgePointSource"]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
