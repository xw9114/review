from threading import BoundedSemaphore

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.config import get_settings
from app.integrations.crawl4ai import Crawl4AIConnector
from app.models import SourceDocument
from app.schemas.source_document import SourceCollectedContent, SourceContentApply, SourceContentPreview, SourceDocumentRead
from app.services.content_quality import content_warnings
from app.services.source_ingestion import _content_hash, _read_model, get_source_document, invalidate_derived_content

_preview_slot = BoundedSemaphore(1)


def _editable(db: Session, source_id: int, revision: int) -> SourceDocument:
    source = get_source_document(db, source_id)
    if source.status != "pending" or not source.provider.startswith("feed:"):
        raise ConflictError("仅待整理的 RSS 资料可以补充正文。")
    if source.content_revision != revision:
        raise ConflictError("资料已在其他页面更新，请刷新后重新预览；本次未覆盖正文。")
    return source


def preview_content(db: Session, source_id: int, revision: int, crawler: Crawl4AIConnector) -> SourceContentPreview:
    source = _editable(db, source_id, revision)
    if not source.source_url:
        raise ConflictError("这条资料没有原文地址，请手动粘贴正文。")
    url = source.source_url
    current_chars = len(source.content)
    db.rollback()  # No locks or open transaction during an upstream request.
    if not _preview_slot.acquire(blocking=False):
        raise ConflictError("已有正文正在抓取，请稍后再试。")
    try:
        content = crawler.clean_article(url)
    finally:
        _preview_slot.release()
    source = _editable(db, source_id, revision)
    if source.source_url != url:
        raise ConflictError("抓取期间原文地址已改变，请刷新后重试。")
    warnings = ["自动抽取不保证完整，请检查是否混入导航、评论或缺少公式；确认应用前不会改动资料。"]
    warnings.extend(content_warnings(content, collected=False))
    if len(content) > get_settings().llm_max_source_chars:
        warnings.append(f"AI 只读取前 {get_settings().llm_max_source_chars:,} 字符，建议先精简到需要学习的正文。")
    if len(content) <= current_chars:
        warnings.append("候选正文不比当前内容长，请特别核对是否抓取正确。")
    return SourceContentPreview(source_document_id=source_id, expected_revision=revision, content=content, content_chars=len(content), warnings=warnings)


def collected_content(db: Session, source_id: int) -> SourceCollectedContent:
    source = get_source_document(db, source_id)
    return SourceCollectedContent(title=source.collected_title or source.title, content=source.collected_content if source.collected_content is not None else source.content)


def apply_content(db: Session, source_id: int, payload: SourceContentApply) -> SourceDocumentRead:
    source = _editable(db, source_id, payload.expected_revision)
    digest = _content_hash(source.title, payload.content)
    if source.content_origin == "supplement" and digest == source.content_hash:
        return _read_model(source)
    if source.collected_content is None:
        source.collected_title, source.collected_content, source.collected_hash = source.title, source.content, source.content_hash
    if digest != source.content_hash:
        invalidate_derived_content(source)
    source.content, source.content_hash = payload.content, digest
    source.content_origin = "supplement"
    source.supplement_base_hash = source.collected_hash
    source.content_revision += 1
    db.commit()
    return _read_model(get_source_document(db, source_id))


def restore_content(db: Session, source_id: int, revision: int) -> SourceDocumentRead:
    source = _editable(db, source_id, revision)
    if source.content_origin == "collected":
        return _read_model(source)
    title = source.collected_title or source.title
    content = source.collected_content if source.collected_content is not None else source.content
    digest = _content_hash(title, content)
    if digest != source.content_hash:
        invalidate_derived_content(source)
    source.title, source.content, source.content_hash = title, content, digest
    source.content_origin = "collected"
    source.supplement_base_hash = None
    source.content_revision += 1
    db.commit()
    return _read_model(get_source_document(db, source_id))
