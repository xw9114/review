from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.topic import TopicCreate, TopicRead, TopicUpdate
from app.services import knowledge_structure as service

router = APIRouter(prefix="/topics", tags=["topics"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[TopicRead])
def list_topics(db: DbSession, category_id: int | None = Query(default=None)) -> list[TopicRead]:
    return service.list_topics(db, category_id)


@router.post("", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicCreate, db: DbSession) -> TopicRead:
    return service.create_topic(db, payload)


@router.get("/{topic_id}", response_model=TopicRead)
def get_topic(topic_id: int, db: DbSession) -> TopicRead:
    return service.get_topic(db, topic_id)


@router.patch("/{topic_id}", response_model=TopicRead)
def update_topic(topic_id: int, payload: TopicUpdate, db: DbSession) -> TopicRead:
    return service.update_topic(db, topic_id, payload)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, db: DbSession) -> Response:
    service.delete_topic(db, topic_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

