import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.models import KnowledgePoint, Topic
from app.models.review import ReviewItem, ReviewProgress, ReviewSession
from app.schemas.review import (
    Rating, ReviewAnswer, ReviewHistoryRead, ReviewItemRead, ReviewOverview, ReviewPointRead,
    ReviewSessionRead, ReviewStart,
)

RATING_ORDER = {"again": 0, "hard": 1, "good": 2, "easy": 3}
INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def quiz_hash(point: KnowledgePoint) -> str:
    raw = json.dumps(point.quiz_items or [], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def next_schedule(level: int, rating: Rating, now: datetime) -> tuple[int, datetime]:
    if rating == "again":
        return 1, now + timedelta(minutes=10)
    if rating == "hard":
        return max(1, level - 1), now + timedelta(days=1)
    next_level = min(5, level + (2 if rating == "easy" else 1))
    return next_level, now + timedelta(days=INTERVAL_DAYS[next_level])


def read_session(session: ReviewSession) -> ReviewSessionRead:
    return ReviewSessionRead(
        id=session.id, status=session.status, created_at=session.created_at,
        completed_at=session.completed_at,
        items=[ReviewItemRead(
            id=item.id, knowledge_point_id=item.knowledge_point_id, position=item.position,
            point_name=item.point_name, topic_name=item.topic_name, question=item.question,
            standard_answer=item.standard_answer if item.revealed_at else None,
            user_answer=item.user_answer, revealed_at=item.revealed_at,
            rating=item.rating, answered_at=item.answered_at,
        ) for item in session.items],
    )


def get_session(db: Session, session_id: int) -> ReviewSession:
    session = db.scalar(select(ReviewSession).where(ReviewSession.id == session_id)
                        .options(selectinload(ReviewSession.items)))
    if session is None:
        raise NotFoundError("复习记录不存在。")
    return session


def active_session(db: Session) -> ReviewSession | None:
    return db.scalar(select(ReviewSession).where(ReviewSession.active_key == "single-user")
                     .options(selectinload(ReviewSession.items)))


def overview(db: Session) -> ReviewOverview:
    now = datetime.now(UTC)
    points = db.scalars(select(KnowledgePoint).where(KnowledgePoint.is_active.is_(True))
                        .options(joinedload(KnowledgePoint.topic))).all()
    progress = {row.knowledge_point_id: row for row in db.scalars(select(ReviewProgress))}
    rows = []
    for point in points:
        if not point.quiz_items:
            continue
        current = progress.get(point.id)
        if current and current.quiz_hash != quiz_hash(point):
            current = None
        rows.append(ReviewPointRead(
            knowledge_point_id=point.id, name=point.name, topic_id=point.topic_id,
            topic_name=point.topic.name, level=current.level if current else 1,
            question_count=len(point.quiz_items), review_count=current.review_count if current else 0,
            due_at=current.due_at if current else None,
            is_due=current is None or utc(current.due_at) <= now,
        ))
    rows.sort(key=lambda row: (not row.is_due, utc(row.due_at) if row.due_at else datetime.min.replace(tzinfo=UTC), row.knowledge_point_id))
    day_start = now.astimezone(ZoneInfo("Asia/Shanghai")).replace(hour=0, minute=0, second=0, microsecond=0)
    reviewed_today = db.scalar(select(func.count()).select_from(ReviewItem).where(
        ReviewItem.answered_at >= day_start,
    )) or 0
    completed = db.scalar(select(func.count()).select_from(ReviewSession).where(
        ReviewSession.status == "completed",
    )) or 0
    active = active_session(db)
    recent = db.execute(select(ReviewSession.id, ReviewSession.completed_at, func.count(ReviewItem.id))
                        .join(ReviewItem).where(ReviewSession.status == "completed")
                        .group_by(ReviewSession.id, ReviewSession.completed_at)
                        .order_by(ReviewSession.completed_at.desc(), ReviewSession.id.desc()).limit(10)).all()
    return ReviewOverview(
        due_count=sum(row.is_due for row in rows), reviewed_today=reviewed_today,
        completed_sessions=completed, active_session_id=active.id if active else None, points=rows,
        recent_sessions=[ReviewHistoryRead(id=row[0], completed_at=row[1], question_count=row[2]) for row in recent],
    )


def start_session(db: Session, payload: ReviewStart) -> ReviewSessionRead:
    existing = active_session(db)
    if existing:
        return read_session(existing)
    if payload.topic_id is not None and db.get(Topic, payload.topic_id) is None:
        raise NotFoundError("主题不存在。")
    candidates = overview(db).points
    if payload.knowledge_point_id is not None:
        if db.get(KnowledgePoint, payload.knowledge_point_id) is None:
            raise NotFoundError("知识点不存在。")
        candidates = [row for row in candidates if row.knowledge_point_id == payload.knowledge_point_id]
    else:
        candidates = [row for row in candidates if row.is_due]
    if payload.topic_id is not None:
        candidates = [row for row in candidates if row.topic_id == payload.topic_id]
    candidates = candidates[:payload.limit]
    if not candidates:
        raise ConflictError("当前没有可复习的题目，请先审核入库或为知识点补充题目。")
    session = ReviewSession(active_key="single-user", status="active")
    for row in candidates:
        point = db.get(KnowledgePoint, row.knowledge_point_id)
        if point is None or not point.quiz_items:
            continue
        for quiz in point.quiz_items:
            session.items.append(ReviewItem(
                knowledge_point_id=point.id, position=len(session.items), point_name=point.name,
                topic_name=row.topic_name, quiz_hash=quiz_hash(point), question=quiz["question"],
                standard_answer=quiz["answer"], user_answer="",
            ))
    if not session.items:
        raise ConflictError("题目已变更，请刷新复习列表。")
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = active_session(db)
        if existing:
            return read_session(existing)
        raise ConflictError("复习队列已变更，请重试。") from None
    return read_session(session)


def locked_item(db: Session, item_id: int) -> tuple[ReviewSession, ReviewItem]:
    session_id = db.scalar(select(ReviewItem.session_id).where(ReviewItem.id == item_id))
    if session_id is None:
        raise NotFoundError("复习题目不存在。")
    session = db.scalar(select(ReviewSession).where(ReviewSession.id == session_id)
                        .with_for_update().execution_options(populate_existing=True))
    if session is None:
        raise NotFoundError("复习记录不存在。")
    db.expire(session, ["items"])
    item = next(row for row in session.items if row.id == item_id)
    return session, item


def reveal(db: Session, item_id: int, user_answer: str) -> ReviewSessionRead:
    session, item = locked_item(db, item_id)
    if item.revealed_at is None:
        item.user_answer = user_answer.strip()
        item.revealed_at = datetime.now(UTC)
        db.commit()
    return read_session(session)


def answer(db: Session, item_id: int, payload: ReviewAnswer) -> ReviewSessionRead:
    session, item = locked_item(db, item_id)
    if item.rating is not None:
        if item.rating != payload.rating or item.user_answer != payload.user_answer.strip():
            raise ConflictError("这道题已记录过，请刷新查看最新进度。")
        return read_session(session)
    if item.revealed_at is None:
        raise ConflictError("请先查看标准答案，再评价掌握程度。")
    now = datetime.now(UTC)
    item.user_answer = payload.user_answer.strip()
    item.rating = payload.rating
    item.answered_at = now
    # Schedule each knowledge point once, using the weakest answer across its questions.
    group = [row for row in session.items if row.knowledge_point_id == item.knowledge_point_id]
    if item.knowledge_point_id and all(row.rating for row in group):
        point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.id == item.knowledge_point_id)
                          .with_for_update())
        if point and point.is_active and quiz_hash(point) == item.quiz_hash:
            progress = db.get(ReviewProgress, point.id)
            unchanged = progress is not None and progress.quiz_hash == item.quiz_hash
            level = progress.level if unchanged else 1
            rating = cast(Rating, min((row.rating for row in group), key=lambda value: RATING_ORDER[value]))
            level, due_at = next_schedule(level, rating, now)
            count = progress.review_count if unchanged else 0
            again_streak = progress.again_streak if unchanged else 0
            total_again = progress.total_again if unchanged else 0
            total_hard = progress.total_hard if unchanged else 0
            if progress is None:
                progress = ReviewProgress(knowledge_point_id=point.id)
                db.add(progress)
            progress.quiz_hash = item.quiz_hash
            progress.level = level
            progress.review_count = count + 1
            progress.last_reviewed_at = now
            progress.due_at = due_at
            # Deterministic weak-point signal for Phase 5 analysis: plain counters, no model call.
            progress.again_streak = again_streak + 1 if rating == "again" else 0
            progress.total_again = total_again + (rating == "again")
            progress.total_hard = total_hard + (rating == "hard")
    if all(row.rating for row in session.items):
        session.status = "completed"
        session.active_key = None
        session.completed_at = now
    db.commit()
    return read_session(session)
