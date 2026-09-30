from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.knowledge_point import (
    KnowledgePointCreate,
    KnowledgePointRead,
    KnowledgePointUpdate,
)
from app.services import knowledge_structure as service

router = APIRouter(prefix="/knowledge-points", tags=["knowledge-points"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[KnowledgePointRead])
def list_knowledge_points(
    db: DbSession, topic_id: int | None = Query(default=None)
) -> list[KnowledgePointRead]:
    return service.list_knowledge_points(db, topic_id)


@router.post("", response_model=KnowledgePointRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_point(payload: KnowledgePointCreate, db: DbSession) -> KnowledgePointRead:
    return service.create_knowledge_point(db, payload)


@router.get("/{knowledge_point_id}", response_model=KnowledgePointRead)
def get_knowledge_point(knowledge_point_id: int, db: DbSession) -> KnowledgePointRead:
    return service.get_knowledge_point(db, knowledge_point_id)


@router.patch("/{knowledge_point_id}", response_model=KnowledgePointRead)
def update_knowledge_point(
    knowledge_point_id: int, payload: KnowledgePointUpdate, db: DbSession
) -> KnowledgePointRead:
    return service.update_knowledge_point(db, knowledge_point_id, payload)


@router.delete("/{knowledge_point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_point(knowledge_point_id: int, db: DbSession) -> Response:
    service.delete_knowledge_point(db, knowledge_point_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

