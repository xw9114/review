from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TopicCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = None
    sort_order: int = 0


class TopicUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = None
    sort_order: int | None = None


class TopicRead(ORMModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

