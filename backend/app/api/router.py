from fastapi import APIRouter

from app.api.routes import (
    categories,
    feed_sources,
    knowledge_drafts,
    knowledge_points,
    reviews,
    source_documents,
    topics,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(categories.router)
api_router.include_router(topics.router)
api_router.include_router(knowledge_points.router)
api_router.include_router(reviews.router)
api_router.include_router(knowledge_drafts.router)
api_router.include_router(source_documents.router)
api_router.include_router(feed_sources.router)
