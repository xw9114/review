from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


SourceStatus = Literal["pending", "accepted", "ignored", "stale"]
ProcessingStatus = Literal["unscored", "scored", "failed"]
RelevanceMethod = Literal["embedding", "keyword"]


class NotebookEntry(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=10000)
    created_at: datetime


class NotebookSnapshot(BaseModel):
    items: list[NotebookEntry]
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "NotebookSnapshot":
        identifiers = [item.external_id for item in self.items]
        if self.total != len(self.items):
            raise ValueError("snapshot total does not match item count")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("snapshot contains duplicate external ids")
        return self


class SourceDocumentRead(BaseModel):
    id: int
    feed_source_id: int | None
    provider: str
    source_name: str
    external_id: str
    title: str
    content: str
    content_hash: str
    content_origin: Literal["collected", "supplement"]
    content_revision: int
    content_chars: int
    content_warnings: list[str]
    ai_input_chars: int
    ai_input_truncated: bool
    collected_changed: bool
    can_supplement: bool
    status: SourceStatus
    source_created_at: datetime
    last_seen_at: datetime
    source_url: str | None
    author: str | None
    knowledge_point_id: int | None
    relevance_score: float | None
    relevance_passed: bool | None
    suggested_topic_id: int | None
    relevance_method: RelevanceMethod | None
    relevance_reason: str | None
    processing_status: ProcessingStatus
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceContentVersion(BaseModel):
    expected_revision: int = Field(ge=1)


class SourceContentApply(SourceContentVersion):
    content: str = Field(min_length=1, max_length=50000)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.replace("\r\n", "\n").replace("\r", "\n").strip() if isinstance(value, str) else value


class SourceContentPreview(BaseModel):
    source_document_id: int
    expected_revision: int
    content: str
    content_chars: int
    warnings: list[str]


class SourceCollectedContent(BaseModel):
    title: str
    content: str


class SourceSyncResult(BaseModel):
    created: int
    updated: int
    unchanged: int
    stale: int
    total: int


class SourceScoreBatchResult(BaseModel):
    requested: int
    scored: int
    failed: int
    embedding: int
    keyword: int
    passed: int
    threshold: float


class SourceDocumentAccept(BaseModel):
    topic_id: int
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
