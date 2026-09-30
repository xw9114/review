from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Rating = Literal["again", "hard", "good", "easy"]


class ReviewStart(BaseModel):
    knowledge_point_id: int | None = Field(default=None, gt=0)
    topic_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=10)


class ReviewReveal(BaseModel):
    user_answer: str = Field(default="", max_length=10000)


class ReviewAnswer(ReviewReveal):
    rating: Rating


class ReviewItemRead(BaseModel):
    id: int
    knowledge_point_id: int | None
    position: int
    point_name: str
    topic_name: str
    question: str
    standard_answer: str | None
    user_answer: str
    revealed_at: datetime | None
    rating: Rating | None
    answered_at: datetime | None


class ReviewSessionRead(BaseModel):
    id: int
    status: Literal["active", "completed"]
    created_at: datetime
    completed_at: datetime | None
    items: list[ReviewItemRead]


class ReviewPointRead(BaseModel):
    knowledge_point_id: int
    name: str
    topic_id: int
    topic_name: str
    level: int
    question_count: int
    review_count: int
    due_at: datetime | None
    is_due: bool


class ReviewHistoryRead(BaseModel):
    id: int
    completed_at: datetime
    question_count: int


class ReviewOverview(BaseModel):
    due_count: int
    reviewed_today: int
    completed_sessions: int
    active_session_id: int | None
    points: list[ReviewPointRead]
    recent_sessions: list[ReviewHistoryRead]
