from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import knowledge_structure as service

router = APIRouter(prefix="/categories", tags=["categories"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[CategoryRead])
def list_categories(db: DbSession) -> list[CategoryRead]:
    return service.list_categories(db)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: DbSession) -> CategoryRead:
    return service.create_category(db, payload)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, db: DbSession) -> CategoryRead:
    return service.get_category(db, category_id)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, payload: CategoryUpdate, db: DbSession) -> CategoryRead:
    return service.update_category(db, category_id, payload)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: DbSession) -> Response:
    service.delete_category(db, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

