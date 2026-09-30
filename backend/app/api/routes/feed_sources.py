from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.integrations.crawl4ai import Crawl4AIConnector, get_crawl4ai_connector
from app.integrations.feed import FeedConnector, get_feed_connector
from app.schemas.feed_source import (
    FeedSourceCreate,
    FeedSourceRead,
    FeedSourceUpdate,
    FeedSyncBatchResult,
    FeedSyncResult,
)
from app.services import feed_ingestion as service

router = APIRouter(prefix="/feed-sources", tags=["feed-sources"])
DbSession = Annotated[Session, Depends(get_db)]
Feed = Annotated[FeedConnector, Depends(get_feed_connector)]
Crawler = Annotated[Crawl4AIConnector, Depends(get_crawl4ai_connector)]


@router.get("", response_model=list[FeedSourceRead])
def list_feed_sources(db: DbSession) -> list[FeedSourceRead]:
    return service.list_feed_sources(db)


@router.post("", response_model=FeedSourceRead, status_code=201)
def create_feed_source(payload: FeedSourceCreate, db: DbSession) -> FeedSourceRead:
    return service.create_feed_source(db, payload)


@router.patch("/{feed_source_id}", response_model=FeedSourceRead)
def update_feed_source(
    feed_source_id: int, payload: FeedSourceUpdate, db: DbSession
) -> FeedSourceRead:
    return service.update_feed_source(db, feed_source_id, payload)


@router.post("/sync-all", response_model=FeedSyncBatchResult)
def sync_all_feed_sources(db: DbSession, feed: Feed, crawler: Crawler) -> FeedSyncBatchResult:
    return service.sync_all_feed_sources(db, feed, crawler)


@router.post("/{feed_source_id}/sync", response_model=FeedSyncResult)
def sync_feed_source(
    feed_source_id: int, db: DbSession, feed: Feed, crawler: Crawler
) -> FeedSyncResult:
    return service.sync_feed_source(db, feed_source_id, feed, crawler)
