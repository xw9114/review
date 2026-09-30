from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.integrations.crawl4ai import Crawl4AIConnector
from app.integrations.feed import FeedConnector
from app.models import FeedSource
from app.schemas.feed_source import (
    CleaningMode,
    FeedSourceCreate,
    FeedSourceRead,
    FeedSourceUpdate,
    FeedSyncBatchResult,
    FeedSyncResult,
)
from app.services.source_ingestion import SourceEntry, upsert_source_entries


def _read_model(source: FeedSource) -> FeedSourceRead:
    return FeedSourceRead.model_validate(source)


def list_feed_sources(db: Session) -> list[FeedSourceRead]:
    query = select(FeedSource).order_by(FeedSource.enabled.desc(), FeedSource.name, FeedSource.id)
    return [_read_model(source) for source in db.scalars(query)]


def get_feed_source(db: Session, feed_source_id: int) -> FeedSource:
    source = db.get(FeedSource, feed_source_id)
    if source is None:
        raise NotFoundError("订阅源不存在。")
    return source


def create_feed_source(db: Session, payload: FeedSourceCreate) -> FeedSourceRead:
    source = FeedSource(**payload.model_dump())
    db.add(source)
    try:
        db.commit()
        db.refresh(source)
        return _read_model(source)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("已经存在同名订阅源。") from exc


def update_feed_source(
    db: Session, feed_source_id: int, payload: FeedSourceUpdate
) -> FeedSourceRead:
    source = get_feed_source(db, feed_source_id)
    changes = payload.model_dump(exclude_unset=True)
    merged = FeedSourceCreate(
        name=changes.get("name", source.name),
        source_type=changes.get("source_type", source.source_type),
        endpoint=changes.get("endpoint", source.endpoint),
        cleaning_mode=changes.get("cleaning_mode", source.cleaning_mode),
        enabled=changes.get("enabled", source.enabled),
    )
    for field, value in merged.model_dump().items():
        setattr(source, field, value)
    try:
        db.commit()
        db.refresh(source)
        return _read_model(source)
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("已经存在同名订阅源。") from exc


def _record_failure(db: Session, source: FeedSource, error: DomainError) -> None:
    source.last_synced_at = datetime.now(UTC)
    source.last_sync_status = "failed"
    source.last_error = error.message[:1000]
    source.last_created = 0
    source.last_updated = 0
    source.last_unchanged = 0
    source.last_failed = 0
    source.last_cleaned = 0
    db.commit()


def sync_feed_source(
    db: Session,
    feed_source_id: int,
    feed: FeedConnector,
    crawler: Crawl4AIConnector,
) -> FeedSyncResult:
    source = get_feed_source(db, feed_source_id)
    if not source.enabled:
        raise ConflictError("订阅源已停用，启用后才能同步。")
    try:
        entries = feed.fetch_entries(source)
    except DomainError as exc:
        _record_failure(db, source, exc)
        raise

    settings = get_settings()
    cleaned_entries: list[SourceEntry] = []
    failed = cleaned = clean_failed = crawl_attempts = 0
    mode = cast(CleaningMode, source.cleaning_mode)

    for entry in entries:
        content = entry.content
        needs_crawl = mode == "crawl4ai" or (
            mode == "auto" and len(content.strip()) < settings.feed_auto_crawl_threshold
        )
        if needs_crawl:
            can_attempt = bool(entry.source_url) and crawl_attempts < settings.feed_max_crawl_items
            if can_attempt:
                crawl_attempts += 1
                try:
                    content = crawler.clean(entry.source_url or "")
                    cleaned += 1
                except DomainError:
                    if mode == "crawl4ai":
                        failed += 1
                        continue
                    clean_failed += 1
            elif mode == "crawl4ai":
                failed += 1
                continue
            else:
                clean_failed += 1

        cleaned_entries.append(
            SourceEntry(
                external_id=entry.external_id,
                title=entry.title,
                content=content,
                created_at=entry.created_at,
                source_url=entry.source_url,
                author=entry.author,
            )
        )

    result = upsert_source_entries(
        db,
        cleaned_entries,
        provider=f"feed:{source.id}",
        feed_source_id=source.id,
        mark_missing_stale=False,
    )
    source.last_synced_at = datetime.now(UTC)
    source.last_sync_status = "partial" if failed or clean_failed else "success"
    source.last_error = (
        f"{failed} 条未导入，{clean_failed} 条使用 Feed 正文回退。"
        if failed or clean_failed
        else None
    )
    source.last_created = result.created
    source.last_updated = result.updated
    source.last_unchanged = result.unchanged
    source.last_failed = failed + clean_failed
    source.last_cleaned = cleaned
    db.commit()

    return FeedSyncResult(
        feed_source_id=source.id,
        feed_source_name=source.name,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        failed=failed,
        cleaned=cleaned,
        clean_failed=clean_failed,
        total=len(entries),
    )


def sync_all_feed_sources(
    db: Session,
    feed: FeedConnector,
    crawler: Crawl4AIConnector,
) -> FeedSyncBatchResult:
    ids = list(db.scalars(select(FeedSource.id).where(FeedSource.enabled.is_(True))))
    results: list[FeedSyncResult] = []
    failed_sources = 0
    for feed_source_id in ids:
        try:
            results.append(sync_feed_source(db, feed_source_id, feed, crawler))
        except DomainError:
            failed_sources += 1

    return FeedSyncBatchResult(
        sources=len(ids),
        succeeded=len(results),
        failed_sources=failed_sources,
        created=sum(result.created for result in results),
        updated=sum(result.updated for result in results),
        unchanged=sum(result.unchanged for result in results),
        failed=sum(result.failed for result in results),
        cleaned=sum(result.cleaned for result in results),
        clean_failed=sum(result.clean_failed for result in results),
        total=sum(result.total for result in results),
        results=results,
    )
