from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


DraftStatus = Literal["draft", "approved", "rejected", "stale"]
Difficulty = Literal["beginner", "intermediate", "advanced"]


class QuizItem(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("question", "answer", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class DraftContent(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=6000)
    difficulty: Difficulty
    key_points: list[str] = Field(min_length=1, max_length=8)
    quiz_items: list[QuizItem] = Field(min_length=1, max_length=5)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("key_points")
    @classmethod
    def validate_key_points(cls, value: list[str]) -> list[str]:
        stripped = [item.strip() for item in value]
        if any(not item or len(item) > 300 for item in stripped):
            raise ValueError("key points must contain 1 to 300 characters")
        return stripped


class KnowledgeDraftGenerate(BaseModel):
    topic_id: int
    regenerate: bool = False
    expected_revision: int | None = Field(default=None, ge=1)


class KnowledgeDraftReview(DraftContent):
    topic_id: int
    expected_revision: int | None = Field(default=None, ge=1)


class KnowledgeDraftRead(DraftContent):
    id: int
    revision: int
    source_document_id: int
    source_title: str
    source_name: str
    source_url: str | None
    source_content_hash: str
    source_status: str
    topic_id: int | None
    status: DraftStatus
    model: str
    prompt_version: str
    generation_count: int
    generated_at: datetime
    reviewed_at: datetime | None
    knowledge_point_id: int | None
    created_at: datetime
    updated_at: datetime
