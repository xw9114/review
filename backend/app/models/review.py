from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ReviewProgress(Base):
    __tablename__ = "review_progress"
    __table_args__ = (CheckConstraint("level BETWEEN 1 AND 5", name="ck_review_progress_level"),)

    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True
    )
    quiz_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[int] = mapped_column(default=1, nullable=False)
    review_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ReviewSession(Base):
    __tablename__ = "review_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed')", name="ck_review_sessions_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # A unique non-null key permits only one active session in this single-user app.
    active_key: Mapped[str | None] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["ReviewItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ReviewItem.position"
    )


class ReviewItem(Base):
    __tablename__ = "review_items"
    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_review_items_position"),
        CheckConstraint(
            "rating IS NULL OR rating IN ('again', 'hard', 'good', 'easy')",
            name="ck_review_items_rating",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), index=True
    )
    position: Mapped[int] = mapped_column(nullable=False)
    point_name: Mapped[str] = mapped_column(String(160), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quiz_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    standard_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating: Mapped[str | None] = mapped_column(String(10))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session: Mapped["ReviewSession"] = relationship(back_populates="items")
