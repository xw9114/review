from datetime import UTC, datetime
from threading import BoundedSemaphore
from typing import cast

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, NotFoundError
from app.integrations.llm import PROMPT_VERSION, LlmConnector
from app.models import KnowledgeDraft, KnowledgePoint, KnowledgePointSource, SourceDocument, Topic
from app.schemas.knowledge_draft import (
    Difficulty,
    DraftStatus,
    KnowledgeDraftRead,
    KnowledgeDraftReview,
    QuizItem,
)
from app.services.source_ingestion import NOTEBOOK_PROVIDER, get_source_document

_generation_slot = BoundedSemaphore(1)


def _source_name(source: SourceDocument) -> str:
    if source.feed_source is not None:
        return source.feed_source.name
    return "日序" if source.provider == NOTEBOOK_PROVIDER else source.provider


def _read_model(draft: KnowledgeDraft) -> KnowledgeDraftRead:
    source = draft.source_document
    return KnowledgeDraftRead(
        id=draft.id,
        revision=draft.revision,
        source_document_id=source.id,
        source_title=source.title,
        source_name=_source_name(source),
        source_url=source.source_url,
        source_content_hash=draft.source_content_hash,
        source_status=source.status,
        topic_id=draft.topic_id,
        status=cast(DraftStatus, draft.status),
        title=draft.title,
        summary=draft.summary,
        difficulty=cast(Difficulty, draft.difficulty),
        key_points=list(draft.key_points),
        quiz_items=[QuizItem.model_validate(item) for item in draft.quiz_items],
        model=draft.model,
        prompt_version=draft.prompt_version,
        generation_count=draft.generation_count,
        generated_at=draft.generated_at,
        reviewed_at=draft.reviewed_at,
        knowledge_point_id=draft.knowledge_point_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _draft_query():
    return select(KnowledgeDraft).options(
        joinedload(KnowledgeDraft.source_document).joinedload(SourceDocument.feed_source)
    )


def get_draft(db: Session, draft_id: int) -> KnowledgeDraft:
    draft = db.scalar(_draft_query().where(KnowledgeDraft.id == draft_id))
    if draft is None:
        raise NotFoundError("知识草稿不存在。")
    return draft


def read_draft(db: Session, draft_id: int) -> KnowledgeDraftRead:
    return _read_model(get_draft(db, draft_id))


def get_source_draft(db: Session, source_document_id: int) -> KnowledgeDraftRead:
    draft = db.scalar(
        _draft_query().where(KnowledgeDraft.source_document_id == source_document_id)
    )
    if draft is None:
        raise NotFoundError("这条资料还没有 AI 草稿。")
    return _read_model(draft)


def list_drafts(db: Session, status: DraftStatus | None = None) -> list[KnowledgeDraftRead]:
    query = _draft_query()
    if status is not None:
        query = query.where(KnowledgeDraft.status == status)
    query = query.order_by(KnowledgeDraft.updated_at.desc(), KnowledgeDraft.id.desc())
    return [_read_model(draft) for draft in db.scalars(query).unique()]


def generate_draft(
    db: Session,
    *,
    source_document_id: int,
    topic_id: int,
    connector: LlmConnector,
    regenerate: bool = False,
    expected_revision: int | None = None,
) -> KnowledgeDraftRead:
    if not _generation_slot.acquire(blocking=False):
        raise ConflictError("已有草稿正在生成，请稍后再试。")
    try:
        return _generate_draft(db, source_document_id=source_document_id, topic_id=topic_id,
                               connector=connector, regenerate=regenerate,
                               expected_revision=expected_revision)
    finally:
        _generation_slot.release()


def _generate_draft(
    db: Session, *, source_document_id: int, topic_id: int, connector: LlmConnector,
    regenerate: bool, expected_revision: int | None,
) -> KnowledgeDraftRead:
    source = get_source_document(db, source_document_id)
    if source.status != "pending":
        raise ConflictError("只有待整理资料可以生成 AI 草稿。")
    topic = db.scalar(select(Topic).options(joinedload(Topic.category)).where(Topic.id == topic_id))
    if topic is None:
        raise NotFoundError("Topic not found.")

    previous = db.scalar(select(KnowledgeDraft).where(KnowledgeDraft.source_document_id == source.id))
    if previous and expected_revision is not None and previous.revision != expected_revision:
        raise ConflictError("草稿已在其他页面修改，请刷新后重试。")
    if previous and not regenerate:
        return _read_model(previous)
    original_hash = source.content_hash
    original_content_revision = source.content_revision
    original_revision = previous.revision if previous else None
    input_values = dict(source_title=source.title, source_content=source.content,
                        category_name=topic.category.name, topic_name=topic.name,
                        topic_description=topic.description)
    # Avoid holding a database transaction during a remote model call.
    db.rollback()
    content = connector.generate_draft(**input_values)
    source = db.scalar(select(SourceDocument).where(SourceDocument.id == source_document_id)
                       .with_for_update().execution_options(populate_existing=True))
    if source is None or source.status != "pending" or source.content_hash != original_hash or source.content_revision != original_content_revision:
        raise ConflictError("生成期间原资料已变更，请刷新后重新生成。")
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("生成期间主题已被删除。")

    now = datetime.now(UTC)
    draft = db.scalar(
        select(KnowledgeDraft).where(KnowledgeDraft.source_document_id == source.id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if (draft.revision if draft else None) != original_revision:
        raise ConflictError("生成期间草稿已被修改，本次结果未覆盖已有内容。")
    if draft is None:
        draft = KnowledgeDraft(
            source_document_id=source.id,
            source_content_hash=source.content_hash,
            topic_id=topic.id,
            status="draft",
            title=content.title,
            summary=content.summary,
            difficulty=content.difficulty,
            key_points=content.key_points,
            quiz_items=[item.model_dump() for item in content.quiz_items],
            model=connector.model_name,
            prompt_version=PROMPT_VERSION,
            generation_count=1,
            generated_at=now,
        )
        db.add(draft)
    else:
        if draft.status == "approved" and source.content_hash == draft.source_content_hash:
            raise ConflictError("已批准的草稿不能重新生成。")
        draft.source_content_hash = source.content_hash
        draft.topic_id = topic.id
        draft.status = "draft"
        draft.title = content.title
        draft.summary = content.summary
        draft.difficulty = content.difficulty
        draft.key_points = content.key_points
        draft.quiz_items = [item.model_dump() for item in content.quiz_items]
        draft.model = connector.model_name
        draft.prompt_version = PROMPT_VERSION
        draft.generation_count += 1
        draft.generated_at = now
        draft.reviewed_at = None
        draft.knowledge_point_id = None
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("草稿已由另一请求创建，请刷新查看。") from exc
    return get_source_draft(db, source.id)


def _editable_draft(db: Session, draft_id: int, expected_revision: int | None = None) -> KnowledgeDraft:
    source_id = db.scalar(select(KnowledgeDraft.source_document_id).where(KnowledgeDraft.id == draft_id))
    if source_id is None:
        raise NotFoundError("知识草稿不存在。")
    db.scalar(select(SourceDocument).where(SourceDocument.id == source_id).with_for_update())
    draft = get_draft(db, draft_id)
    if expected_revision is not None and draft.revision != expected_revision:
        raise ConflictError("草稿已在其他页面修改，请刷新后重试。")
    if draft.status == "approved":
        raise ConflictError("已批准的草稿不能修改。")
    if draft.status == "stale" or draft.source_document.content_hash != draft.source_content_hash:
        raise ConflictError("原资料已更新，请先重新生成草稿。")
    if draft.source_document.status != "pending":
        raise ConflictError("原资料已处理，无法继续审核这份草稿。")
    return draft


def update_draft(
    db: Session, draft_id: int, payload: KnowledgeDraftReview
) -> KnowledgeDraftRead:
    draft = _editable_draft(db, draft_id, payload.expected_revision)
    if draft.status == "approved":
        raise ConflictError("已批准的草稿不能修改。")
    if draft.status == "stale":
        raise ConflictError("原资料已更新，请先重新生成草稿。")
    if db.get(Topic, payload.topic_id) is None:
        raise NotFoundError("Topic not found.")
    draft.topic_id = payload.topic_id
    draft.status = "draft"
    draft.title = payload.title
    draft.summary = payload.summary
    draft.difficulty = payload.difficulty
    draft.key_points = payload.key_points
    draft.quiz_items = [item.model_dump() for item in payload.quiz_items]
    draft.reviewed_at = None
    db.commit()
    return read_draft(db, draft.id)


def reject_draft(db: Session, draft_id: int, expected_revision: int | None = None) -> KnowledgeDraftRead:
    draft = _editable_draft(db, draft_id, expected_revision)
    if draft.status == "approved":
        raise ConflictError("已批准的草稿不能拒绝。")
    draft.status = "rejected"
    draft.reviewed_at = datetime.now(UTC)
    db.commit()
    return read_draft(db, draft.id)


def approve_draft(
    db: Session, draft_id: int, payload: KnowledgeDraftReview
) -> KnowledgeDraftRead:
    draft = _editable_draft(db, draft_id, payload.expected_revision)
    source = draft.source_document
    if draft.status == "approved":
        raise ConflictError("这份草稿已经批准。")
    if draft.status == "stale" or source.content_hash != draft.source_content_hash:
        raise ConflictError("原资料已更新，请重新生成草稿后再批准。")
    if source.status != "pending":
        raise ConflictError("只有待整理资料可以批准入库。")
    if db.get(Topic, payload.topic_id) is None:
        raise NotFoundError("Topic not found.")
    normalized_slug = slugify(payload.title)
    if not normalized_slug:
        raise ConflictError("A non-empty slug is required for this name.")

    try:
        if source.knowledge_links:
            knowledge_point = source.knowledge_links[0].knowledge_point
            knowledge_point.topic_id = payload.topic_id
            knowledge_point.name = payload.title
            knowledge_point.slug = normalized_slug
        else:
            knowledge_point = KnowledgePoint(
                topic_id=payload.topic_id,
                name=payload.title,
                slug=normalized_slug,
                is_active=True,
                sort_order=0,
            )
            db.add(knowledge_point)
            db.flush()
            db.add(
                KnowledgePointSource(
                    knowledge_point_id=knowledge_point.id,
                    source_document_id=source.id,
                )
            )
        knowledge_point.description = payload.summary
        knowledge_point.summary = payload.summary
        knowledge_point.difficulty = payload.difficulty
        knowledge_point.key_points = payload.key_points
        knowledge_point.quiz_items = [item.model_dump() for item in payload.quiz_items]

        draft.topic_id = payload.topic_id
        draft.title = payload.title
        draft.summary = payload.summary
        draft.difficulty = payload.difficulty
        draft.key_points = payload.key_points
        draft.quiz_items = [item.model_dump() for item in payload.quiz_items]
        draft.status = "approved"
        draft.reviewed_at = datetime.now(UTC)
        draft.knowledge_point_id = knowledge_point.id
        source.status = "accepted"
        db.commit()
        return read_draft(db, draft.id)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "该主题下已有同名知识点，请修改草稿名称。"
        ) from exc
