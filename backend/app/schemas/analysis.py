from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.knowledge_draft import QuizItem

ErrorType = Literal["concept_confusion", "incomplete_recall", "terminology_mixup", "slip", "other"]
VariantStatus = Literal["pending", "approved", "rejected"]


class ErrorAnalysisContent(BaseModel):
    """Validated model output — the only shape trusted before persisting a diagnosis."""

    error_type: ErrorType
    explanation: str = Field(min_length=1, max_length=1000)
    suggestion: str = Field(min_length=1, max_length=1000)


class ErrorAnalysisRead(BaseModel):
    id: int
    knowledge_point_id: int
    point_name: str
    topic_name: str
    error_type: ErrorType
    explanation: str
    suggestion: str
    model: str
    generated_at: datetime


class QuestionVariantsContent(BaseModel):
    """Validated model output for a batch of alternate-phrasing questions."""

    variants: list[QuizItem] = Field(min_length=1, max_length=5)


class QuestionVariantRead(BaseModel):
    id: int
    knowledge_point_id: int
    question: str
    answer: str
    status: VariantStatus
    generated_at: datetime


class GenerateVariantsRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=5)


class WeakPointRead(BaseModel):
    knowledge_point_id: int
    name: str
    topic_id: int
    topic_name: str
    level: int
    again_streak: int
    total_again: int
    review_count: int
    due_at: datetime | None


class AnalysisOverview(BaseModel):
    mastery_distribution: dict[str, int]
    weak_points: list[WeakPointRead]
    error_type_distribution: dict[str, int]
    tips: list[str]
