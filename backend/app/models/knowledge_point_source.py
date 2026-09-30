from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.knowledge_point import KnowledgePoint
    from app.models.source_document import SourceDocument


class KnowledgePointSource(Base):
    __tablename__ = "knowledge_point_sources"
    __table_args__ = (
        UniqueConstraint("source_document_id", name="uq_knowledge_point_sources_document"),
        UniqueConstraint(
            "knowledge_point_id",
            "source_document_id",
            name="uq_knowledge_point_sources_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="source_links")
    source_document: Mapped["SourceDocument"] = relationship(back_populates="knowledge_links")
