from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.knowledge_point import KnowledgePoint


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_topics_category_name"),
        UniqueConstraint("category_id", "slug", name="uq_topics_category_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_input_hash: Mapped[str | None] = mapped_column(String(64))

    category: Mapped["Category"] = relationship(back_populates="topics")
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
