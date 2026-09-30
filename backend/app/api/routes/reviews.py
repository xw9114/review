from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.review import ReviewAnswer, ReviewOverview, ReviewReveal, ReviewSessionRead, ReviewStart
from app.services import reviews

router = APIRouter(prefix="/reviews", tags=["reviews"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/overview", response_model=ReviewOverview)
def overview(db: DbSession):
    return reviews.overview(db)


@router.get("/active", response_model=ReviewSessionRead | None)
def active(db: DbSession):
    session = reviews.active_session(db)
    return reviews.read_session(session) if session else None


@router.post("/sessions", response_model=ReviewSessionRead)
def start(payload: ReviewStart, db: DbSession):
    return reviews.start_session(db, payload)


@router.get("/sessions/{session_id}", response_model=ReviewSessionRead)
def get_session(session_id: int, db: DbSession):
    return reviews.read_session(reviews.get_session(db, session_id))


@router.post("/items/{item_id}/reveal", response_model=ReviewSessionRead)
def reveal(item_id: int, payload: ReviewReveal, db: DbSession):
    return reviews.reveal(db, item_id, payload.user_answer)


@router.post("/items/{item_id}/answer", response_model=ReviewSessionRead)
def answer(item_id: int, payload: ReviewAnswer, db: DbSession):
    return reviews.answer(db, item_id, payload)
