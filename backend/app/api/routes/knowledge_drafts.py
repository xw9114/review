from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.integrations.llm import LlmConnector, get_llm_connector
from app.schemas.knowledge_draft import (
    DraftStatus,
    KnowledgeDraftGenerate,
    KnowledgeDraftRead,
    KnowledgeDraftReview,
)
from app.services import knowledge_drafts as service

router = APIRouter(tags=["knowledge-drafts"])
DbSession = Annotated[Session, Depends(get_db)]
Llm = Annotated[LlmConnector, Depends(get_llm_connector)]


@router.get("/knowledge-drafts", response_model=list[KnowledgeDraftRead])
def list_knowledge_drafts(
    db: DbSession, status: DraftStatus | None = Query(default=None)
) -> list[KnowledgeDraftRead]:
    return service.list_drafts(db, status)


@router.get("/knowledge-drafts/{draft_id}", response_model=KnowledgeDraftRead)
def get_knowledge_draft(draft_id: int, db: DbSession) -> KnowledgeDraftRead:
    return service.read_draft(db, draft_id)


@router.patch("/knowledge-drafts/{draft_id}", response_model=KnowledgeDraftRead)
def update_knowledge_draft(
    draft_id: int, payload: KnowledgeDraftReview, db: DbSession
) -> KnowledgeDraftRead:
    return service.update_draft(db, draft_id, payload)


@router.post("/knowledge-drafts/{draft_id}/approve", response_model=KnowledgeDraftRead)
def approve_knowledge_draft(
    draft_id: int, payload: KnowledgeDraftReview, db: DbSession
) -> KnowledgeDraftRead:
    return service.approve_draft(db, draft_id, payload)


@router.post("/knowledge-drafts/{draft_id}/reject", response_model=KnowledgeDraftRead)
def reject_knowledge_draft(
    draft_id: int, db: DbSession, expected_revision: int | None = Query(default=None, ge=1)
) -> KnowledgeDraftRead:
    return service.reject_draft(db, draft_id, expected_revision)


@router.get(
    "/source-documents/{source_document_id}/draft", response_model=KnowledgeDraftRead
)
def get_source_document_draft(
    source_document_id: int, db: DbSession
) -> KnowledgeDraftRead:
    return service.get_source_draft(db, source_document_id)


@router.post(
    "/source-documents/{source_document_id}/draft/generate",
    response_model=KnowledgeDraftRead,
)
def generate_source_document_draft(
    source_document_id: int,
    payload: KnowledgeDraftGenerate,
    db: DbSession,
    llm: Llm,
) -> KnowledgeDraftRead:
    return service.generate_draft(
        db,
        source_document_id=source_document_id,
        topic_id=payload.topic_id,
        connector=llm,
        regenerate=payload.regenerate,
        expected_revision=payload.expected_revision,
    )
