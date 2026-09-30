from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.source_document import SourceDocument


class FeedSource(TimestampMixin, Base):
    __tablename__ = "feed_sources"
    __table_args__ = (
        UniqueConstraint("name", name="uq_feed_sources_name"),
        CheckConstraint("source_type IN ('rss', 'rsshub')", name="ck_feed_sources_type"),
        CheckConstraint(
            "cleaning_mode IN ('feed', 'auto', 'crawl4ai')",
            name="ck_feed_sources_cleaning_mode",
        ),
        CheckConstraint(
            "last_sync_status IN ('never', 'success', 'partial', 'failed')",
            name="ck_feed_sources_sync_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    cleaning_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str] = mapped_column(String(16), nullable=False, default="never")
    last_error: Mapped[str | None] = mapped_column(Text)
    last_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_cleaned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    documents: Mapped[list["SourceDocument"]] = relationship(back_populates="feed_source")
