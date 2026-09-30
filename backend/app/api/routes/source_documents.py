from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.integrations.embedding import EmbeddingConnector, get_embedding_connector
from app.integrations.crawl4ai import Crawl4AIConnector, get_crawl4ai_connector
from app.integrations.notebook import NotebookConnector, get_notebook_connector
from app.schemas.source_document import (
    SourceDocumentAccept,
    SourceDocumentRead,
    SourceStatus,
    SourceScoreBatchResult,
    SourceSyncResult,
    SourceContentApply,
    SourceContentVersion,
    SourceContentPreview,
    SourceCollectedContent,
)
from app.services import relevance_scoring
from app.services import source_content
from app.services import source_ingestion as service

router = APIRouter(tags=["source-documents"])
DbSession = Annotated[Session, Depends(get_db)]
Notebook = Annotated[NotebookConnector, Depends(get_notebook_connector)]
Embedding = Annotated[EmbeddingConnector, Depends(get_embedding_connector)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Crawler = Annotated[Crawl4AIConnector, Depends(get_crawl4ai_connector)]


@router.get("/source-documents/{source_document_id}/content-collected", response_model=SourceCollectedContent)
def read_collected_content(source_document_id: int, db: DbSession) -> SourceCollectedContent:
    return source_content.collected_content(db, source_document_id)


@router.post("/source-documents/{source_document_id}/content-preview", response_model=SourceContentPreview)
def preview_content(source_document_id: int, payload: SourceContentVersion, db: DbSession, crawler: Crawler) -> SourceContentPreview:
    return source_content.preview_content(db, source_document_id, payload.expected_revision, crawler)


@router.patch("/source-documents/{source_document_id}/content", response_model=SourceDocumentRead)
def apply_content(source_document_id: int, payload: SourceContentApply, db: DbSession) -> SourceDocumentRead:
    return source_content.apply_content(db, source_document_id, payload)


@router.post("/source-documents/{source_document_id}/content-restore", response_model=SourceDocumentRead)
def restore_content(source_document_id: int, payload: SourceContentVersion, db: DbSession) -> SourceDocumentRead:
    return source_content.restore_content(db, source_document_id, payload.expected_revision)


@router.post("/source-connectors/notebook/sync", response_model=SourceSyncResult)
def sync_notebook(db: DbSession, notebook: Notebook) -> SourceSyncResult:
    return service.sync_notebook(db, notebook.fetch_entries())


@router.get("/source-documents", response_model=list[SourceDocumentRead])
def list_source_documents(
    db: DbSession, status: SourceStatus | None = Query(default=None)
) -> list[SourceDocumentRead]:
    return service.list_source_documents(db, status)


@router.post("/source-documents/score-pending", response_model=SourceScoreBatchResult)
def score_pending_source_documents(
    db: DbSession, embedding: Embedding, settings: AppSettings
) -> SourceScoreBatchResult:
    return relevance_scoring.score_pending_sources(db, embedding, settings)


@router.get("/source-documents/{source_document_id}", response_model=SourceDocumentRead)
def get_source_document(source_document_id: int, db: DbSession) -> SourceDocumentRead:
    return service.read_source_document(db, source_document_id)


@router.post(
    "/source-documents/{source_document_id}/score", response_model=SourceDocumentRead
)
def score_source_document(
    source_document_id: int,
    db: DbSession,
    embedding: Embedding,
    settings: AppSettings,
) -> SourceDocumentRead:
    return relevance_scoring.score_source_document(
        db, source_document_id, embedding, settings
    )


@router.post("/source-documents/{source_document_id}/accept", response_model=SourceDocumentRead)
def accept_source_document(
    source_document_id: int, payload: SourceDocumentAccept, db: DbSession
) -> SourceDocumentRead:
    return service.accept_source_document(db, source_document_id, payload)


@router.post("/source-documents/{source_document_id}/ignore", response_model=SourceDocumentRead)
def ignore_source_document(source_document_id: int, db: DbSession) -> SourceDocumentRead:
    return service.ignore_source_document(db, source_document_id)
