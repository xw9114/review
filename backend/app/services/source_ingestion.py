import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.core.config import get_settings
from app.models import KnowledgePoint, KnowledgePointSource, SourceDocument, Topic
from app.schemas.source_document import (
    NotebookEntry,
    ProcessingStatus,
    RelevanceMethod,
    SourceDocumentAccept,
    SourceDocumentRead,
    SourceStatus,
    SourceSyncResult,
)
from app.services.content_quality import content_warnings

NOTEBOOK_PROVIDER = "wechat_notebook"


@dataclass(frozen=True)
class SourceEntry:
    external_id: str
    title: str
    content: str
    created_at: datetime
    source_url: str | None = None
    author: str | None = None


def _content_hash(title: str, content: str) -> str:
    normalized = {
        "title": title.strip(),
        "content": content.replace("\r\n", "\n").replace("\r", "\n").strip(),
    }
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_model(document: SourceDocument) -> SourceDocumentRead:
    knowledge_point_id = (
        document.knowledge_links[0].knowledge_point_id if document.knowledge_links else None
    )
    return SourceDocumentRead(
        id=document.id,
        feed_source_id=document.feed_source_id,
        provider=document.provider,
        source_name=(
            document.feed_source.name
            if document.feed_source is not None
            else ("日序" if document.provider == NOTEBOOK_PROVIDER else document.provider)
        ),
        external_id=document.external_id,
        title=document.title,
        content=document.content,
        content_hash=document.content_hash,
        content_origin=document.content_origin,
        content_revision=document.content_revision,
        content_chars=len(document.content),
        content_warnings=content_warnings(document.content, collected=document.content_origin == "collected" and document.provider.startswith("feed:")),
        ai_input_chars=min(len(document.content), get_settings().llm_max_source_chars),
        ai_input_truncated=len(document.content) > get_settings().llm_max_source_chars,
        collected_changed=bool(document.content_origin == "supplement" and document.collected_hash != document.supplement_base_hash),
        can_supplement=document.status == "pending" and document.provider.startswith("feed:"),
        status=cast(SourceStatus, document.status),
        source_created_at=document.source_created_at,
        last_seen_at=document.last_seen_at,
        source_url=document.source_url,
        author=document.author,
        knowledge_point_id=knowledge_point_id,
        relevance_score=document.relevance_score,
        relevance_passed=document.relevance_passed,
        suggested_topic_id=document.suggested_topic_id,
        relevance_method=(
            cast(RelevanceMethod, document.relevance_method)
            if document.relevance_method is not None
            else None
        ),
        relevance_reason=document.relevance_reason,
        processing_status=cast(ProcessingStatus, document.processing_status),
        processed_at=document.processed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def upsert_source_entries(
    db: Session,
    entries: list[SourceEntry],
    *,
    provider: str,
    feed_source_id: int | None = None,
    mark_missing_stale: bool = False,
) -> SourceSyncResult:
    now = datetime.now(UTC)
    documents = list(
        db.scalars(
            select(SourceDocument)
            .where(SourceDocument.provider == provider)
            .order_by(SourceDocument.id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .options(
                selectinload(SourceDocument.knowledge_links),
                selectinload(SourceDocument.feed_source),
                selectinload(SourceDocument.draft),
            )
        )
    )
    existing = {document.external_id: document for document in documents}
    seen: set[str] = set()
    created = updated = unchanged = stale = 0

    for entry in entries:
        seen.add(entry.external_id)
        digest = _content_hash(entry.title, entry.content)
        document = existing.get(entry.external_id)
        if document is None:
            db.add(
                SourceDocument(
                    provider=provider,
                    feed_source_id=feed_source_id,
                    external_id=entry.external_id,
                    title=entry.title.strip(),
                    content=entry.content,
                    content_hash=digest,
                    collected_title=entry.title.strip(),
                    collected_content=entry.content,
                    collected_hash=digest,
                    status="pending",
                    source_created_at=entry.created_at,
                    last_seen_at=now,
                    source_url=entry.source_url,
                    author=entry.author,
                )
            )
            created += 1
            continue

        upstream_changed = (document.collected_hash or document.content_hash) != digest
        address_changed = document.source_url != entry.source_url
        changed = document.content_origin == "collected" and document.content_hash != digest
        restored = document.status == "stale"
        document.last_seen_at = now
        document.source_created_at = entry.created_at
        document.feed_source_id = feed_source_id
        document.source_url = entry.source_url
        document.author = entry.author
        document.collected_title = entry.title.strip()
        document.collected_content = entry.content
        document.collected_hash = digest
        if upstream_changed or address_changed:
            document.content_revision += 1
        if changed:
            document.title = entry.title.strip()
            document.content = entry.content
            document.content_hash = digest
            document.status = "pending"
            invalidate_derived_content(document)
            updated += 1
        elif restored:
            document.status = "accepted" if document.knowledge_links else "pending"
            updated += 1
        elif upstream_changed or address_changed:
            # Confirmed supplements remain active even when RSS sends a short excerpt.
            updated += 1
        else:
            unchanged += 1

    for external_id, document in existing.items():
        if mark_missing_stale and external_id not in seen and document.status != "stale":
            document.status = "stale"
            stale += 1

    return SourceSyncResult(
        created=created,
        updated=updated,
        unchanged=unchanged,
        stale=stale,
        total=len(entries),
    )


def invalidate_derived_content(document: SourceDocument) -> None:
    document.embedding = None
    document.embedding_model = None
    document.embedding_input_hash = None
    document.relevance_score = None
    document.relevance_passed = None
    document.suggested_topic_id = None
    document.relevance_method = None
    document.relevance_reason = None
    document.processing_status = "unscored"
    document.processed_at = None
    if document.draft is not None:
        document.draft.status = "stale"
        document.draft.reviewed_at = datetime.now(UTC)


def sync_notebook(db: Session, entries: list[NotebookEntry]) -> SourceSyncResult:
    result = upsert_source_entries(
        db,
        [
            SourceEntry(
                external_id=entry.external_id,
                title=entry.title,
                content=entry.content,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
        provider=NOTEBOOK_PROVIDER,
        mark_missing_stale=True,
    )
    db.commit()
    return result


def list_source_documents(
    db: Session, status: SourceStatus | None = None
) -> list[SourceDocumentRead]:
    query = select(SourceDocument).options(
        selectinload(SourceDocument.knowledge_links),
        selectinload(SourceDocument.feed_source),
    )
    if status is not None:
        query = query.where(SourceDocument.status == status)
    query = query.order_by(SourceDocument.source_created_at.desc(), SourceDocument.id.desc())
    return [_read_model(document) for document in db.scalars(query)]


def get_source_document(db: Session, source_document_id: int) -> SourceDocument:
    document = db.scalar(
        select(SourceDocument)
        .where(SourceDocument.id == source_document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
        .options(
            selectinload(SourceDocument.knowledge_links),
            selectinload(SourceDocument.feed_source),
        )
    )
    if document is None:
        raise NotFoundError("Source document not found.")
    return document


def read_source_document(db: Session, source_document_id: int) -> SourceDocumentRead:
    return _read_model(get_source_document(db, source_document_id))


def accept_source_document(
    db: Session, source_document_id: int, payload: SourceDocumentAccept
) -> SourceDocumentRead:
    document = get_source_document(db, source_document_id)
    if document.status == "stale":
        raise ConflictError("失效的资料不能整理为知识点。")
    if document.status == "accepted":
        raise ConflictError("这条资料已经整理过了。")
    if db.get(Topic, payload.topic_id) is None:
        raise NotFoundError("Topic not found.")

    name = payload.name.strip()
    normalized_slug = slugify(name)
    if not normalized_slug:
        raise ConflictError("A non-empty slug is required for this name.")

    try:
        if document.knowledge_links:
            knowledge_point = document.knowledge_links[0].knowledge_point
            knowledge_point.topic_id = payload.topic_id
            knowledge_point.name = name
            knowledge_point.slug = normalized_slug
            knowledge_point.description = payload.description
            knowledge_point.is_active = True
        else:
            knowledge_point = KnowledgePoint(
                topic_id=payload.topic_id,
                name=name,
                slug=normalized_slug,
                description=payload.description,
                is_active=True,
                sort_order=0,
            )
            db.add(knowledge_point)
            db.flush()
            db.add(
                KnowledgePointSource(
                    knowledge_point_id=knowledge_point.id,
                    source_document_id=document.id,
                )
            )
        document.status = "accepted"
        # A manual re-import has no reviewed structured questions for the new content.
        knowledge_point.summary = None
        knowledge_point.difficulty = None
        knowledge_point.key_points = None
        knowledge_point.quiz_items = None
        if document.draft is not None and document.draft.status != "approved":
            document.draft.status = "rejected"
            document.draft.reviewed_at = datetime.now(UTC)
        db.commit()
        db.refresh(document)
        document = get_source_document(db, document.id)
        return _read_model(document)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A knowledge point with this name or slug already exists in the topic."
        ) from exc


def ignore_source_document(db: Session, source_document_id: int) -> SourceDocumentRead:
    document = get_source_document(db, source_document_id)
    if document.status == "accepted":
        raise ConflictError("已整理的资料不能直接忽略。")
    if document.status == "stale":
        raise ConflictError("失效资料无需忽略。")
    document.status = "ignored"
    if document.draft is not None and document.draft.status != "approved":
        document.draft.status = "rejected"
        document.draft.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(document)
    return _read_model(document)
