from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.knowledge_draft import Difficulty, QuizItem


class KnowledgePointCreate(BaseModel):
    topic_id: int
    name: str = Field(min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = None
    summary: str | None = Field(default=None, max_length=6000)
    difficulty: Difficulty | None = None
    key_points: list[str] | None = None
    quiz_items: list[QuizItem] | None = Field(default=None, max_length=5)
    is_active: bool = True
    sort_order: int = 0


class KnowledgePointUpdate(BaseModel):
    topic_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    summary: str | None = Field(default=None, max_length=6000)
    difficulty: Difficulty | None = None
    key_points: list[str] | None = None
    quiz_items: list[QuizItem] | None = Field(default=None, max_length=5)
    is_active: bool | None = None
    sort_order: int | None = None


class KnowledgePointRead(ORMModel):
    id: int
    topic_id: int
    name: str
    slug: str
    description: str | None
    summary: str | None
    difficulty: Difficulty | None
    key_points: list[str] | None
    quiz_items: list[QuizItem] | None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    source_document_ids: list[int] = Field(default_factory=list)
