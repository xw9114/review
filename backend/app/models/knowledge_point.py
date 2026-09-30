from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.knowledge_point_source import KnowledgePointSource
    from app.models.topic import Topic


class KnowledgePoint(TimestampMixin, Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        UniqueConstraint("topic_id", "name", name="uq_knowledge_points_topic_name"),
        UniqueConstraint("topic_id", "slug", name="uq_knowledge_points_topic_slug"),
        CheckConstraint(
            "difficulty IS NULL OR difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_knowledge_points_difficulty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(16))
    key_points: Mapped[list[str] | None] = mapped_column(JSON)
    quiz_items: Mapped[list[dict[str, str]] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    topic: Mapped["Topic"] = relationship(back_populates="knowledge_points")
    source_links: Mapped[list["KnowledgePointSource"]] = relationship(
        back_populates="knowledge_point", cascade="all, delete-orphan",
        passive_deletes=True, lazy="selectin"
    )

    @property
    def source_document_ids(self) -> list[int]:
        return [link.source_document_id for link in self.source_links]
