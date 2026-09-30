from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, NotFoundError
from app.integrations.llm import (
    ERROR_ANALYSIS_PROMPT_VERSION,
    GENERATION_SLOT,
    QUESTION_VARIANTS_PROMPT_VERSION,
    LlmConnector,
)
from app.models.analysis import ErrorAnalysis, QuestionVariant
from app.models.knowledge_point import KnowledgePoint
from app.models.review import ReviewItem, ReviewProgress
from app.schemas.analysis import (
    AnalysisOverview,
    ErrorAnalysisRead,
    QuestionVariantRead,
    VariantStatus,
    WeakPointRead,
)

# A point counts as "weak" once recent answers keep landing on "again", or it has stayed
# stuck at the lowest levels despite repeated review — both plain counter thresholds, no model.
WEAK_AGAIN_STREAK = 2
WEAK_LEVEL_CEILING = 2
WEAK_MIN_REVIEWS = 3
MAX_WEAK_POINTS = 10

ERROR_TYPE_LABELS = {
    "concept_confusion": "概念混淆", "incomplete_recall": "记忆不完整",
    "terminology_mixup": "术语混淆", "slip": "偶然失误", "other": "其他",
}


def _error_analysis_read(row: ErrorAnalysis, point: KnowledgePoint) -> ErrorAnalysisRead:
    return ErrorAnalysisRead(
        id=row.id, knowledge_point_id=row.knowledge_point_id, point_name=point.name,
        topic_name=point.topic.name, error_type=row.error_type, explanation=row.explanation,
        suggestion=row.suggestion, model=row.model, generated_at=row.generated_at,
    )


def _variant_read(row: QuestionVariant) -> QuestionVariantRead:
    return QuestionVariantRead(
        id=row.id, knowledge_point_id=row.knowledge_point_id, question=row.question,
        answer=row.answer, status=row.status, generated_at=row.generated_at,
    )


def _active_point(db: Session, point_id: int) -> KnowledgePoint:
    point = db.scalar(
        select(KnowledgePoint).options(joinedload(KnowledgePoint.topic))
        .where(KnowledgePoint.id == point_id)
    )
    if point is None or not point.is_active:
        raise NotFoundError("知识点不存在。")
    return point


def _wrong_answers(db: Session, point_id: int, limit: int = 5) -> list[dict[str, str]]:
    rows = db.scalars(
        select(ReviewItem).where(
            ReviewItem.knowledge_point_id == point_id, ReviewItem.rating.in_(["again", "hard"])
        ).order_by(ReviewItem.answered_at.desc()).limit(limit)
    ).all()
    return [
        {
            "question": row.question, "standard_answer": row.standard_answer,
            "user_answer": row.user_answer, "rating": row.rating or "",
        }
        for row in rows
    ]


def overview(db: Session) -> AnalysisOverview:
    points = db.scalars(
        select(KnowledgePoint).where(KnowledgePoint.is_active.is_(True))
        .options(joinedload(KnowledgePoint.topic))
    ).all()
    progress = {row.knowledge_point_id: row for row in db.scalars(select(ReviewProgress))}

    mastery_distribution = {str(level): 0 for level in range(1, 6)}
    weak_rows: list[WeakPointRead] = []
    for point in points:
        current = progress.get(point.id)
        if current is None:
            continue
        mastery_distribution[str(current.level)] += 1
        is_weak = (
            current.again_streak >= WEAK_AGAIN_STREAK
            or (current.level <= WEAK_LEVEL_CEILING and current.review_count >= WEAK_MIN_REVIEWS)
        )
        if is_weak:
            weak_rows.append(WeakPointRead(
                knowledge_point_id=point.id, name=point.name, topic_id=point.topic_id,
                topic_name=point.topic.name, level=current.level, again_streak=current.again_streak,
                total_again=current.total_again, review_count=current.review_count,
                due_at=current.due_at,
            ))
    weak_rows.sort(key=lambda row: (-row.again_streak, row.level))
    weak_rows = weak_rows[:MAX_WEAK_POINTS]

    error_type_distribution = {label: 0 for label in ERROR_TYPE_LABELS}
    for error_type in db.scalars(select(ErrorAnalysis.error_type)):
        error_type_distribution[error_type] = error_type_distribution.get(error_type, 0) + 1

    tips: list[str] = []
    for row in weak_rows[:3]:
        if row.again_streak >= WEAK_AGAIN_STREAK:
            tips.append(f"「{row.name}」连续 {row.again_streak} 次评价为「没记住」，建议今天优先复习。")
        else:
            tips.append(f"「{row.name}」长期停留在 L{row.level}，可以试试为它生成变式题换个角度巩固。")
    stuck_count = sum(
        1 for row in weak_rows if row.again_streak < WEAK_AGAIN_STREAK and row.level <= WEAK_LEVEL_CEILING
    )
    if stuck_count >= 3:
        tips.append(f"有 {stuck_count} 个知识点长期停留在 L1/L2，建议逐个补充变式题或重新梳理理解。")
    if not weak_rows and points:
        tips.append("最近没有明显的薄弱知识点，继续保持当前的复习节奏。")

    return AnalysisOverview(
        mastery_distribution=mastery_distribution, weak_points=weak_rows,
        error_type_distribution=error_type_distribution, tips=tips,
    )


def get_error_analysis(db: Session, point_id: int) -> ErrorAnalysisRead:
    point = _active_point(db, point_id)
    row = db.scalar(select(ErrorAnalysis).where(ErrorAnalysis.knowledge_point_id == point_id))
    if row is None:
        raise NotFoundError("这个知识点还没有错题分析。")
    return _error_analysis_read(row, point)


def generate_error_analysis(db: Session, point_id: int, connector: LlmConnector) -> ErrorAnalysisRead:
    if not GENERATION_SLOT.acquire(blocking=False):
        raise ConflictError("已有分析正在生成，请稍后再试。")
    try:
        return _generate_error_analysis(db, point_id, connector)
    finally:
        GENERATION_SLOT.release()


def _generate_error_analysis(db: Session, point_id: int, connector: LlmConnector) -> ErrorAnalysisRead:
    point = _active_point(db, point_id)
    wrong_answers = _wrong_answers(db, point_id)
    if not wrong_answers:
        raise ConflictError("该知识点还没有答错的题目可供分析。")
    point_name, summary, key_points = point.name, point.summary, point.key_points
    # Avoid holding a database transaction during a remote model call.
    db.rollback()
    content = connector.classify_error(
        point_name=point_name, summary=summary, key_points=key_points, wrong_answers=wrong_answers
    )
    point = _active_point(db, point_id)
    now = datetime.now(UTC)
    row = db.scalar(select(ErrorAnalysis).where(ErrorAnalysis.knowledge_point_id == point_id))
    if row is None:
        row = ErrorAnalysis(knowledge_point_id=point_id)
        db.add(row)
    row.error_type = content.error_type
    row.explanation = content.explanation
    row.suggestion = content.suggestion
    row.input_snapshot = wrong_answers
    row.model = connector.model_name
    row.prompt_version = ERROR_ANALYSIS_PROMPT_VERSION
    row.generated_at = now
    db.commit()
    return _error_analysis_read(row, point)


def list_question_variants(
    db: Session, point_id: int, status: VariantStatus | None = None
) -> list[QuestionVariantRead]:
    _active_point(db, point_id)
    query = select(QuestionVariant).where(QuestionVariant.knowledge_point_id == point_id)
    if status is not None:
        query = query.where(QuestionVariant.status == status)
    query = query.order_by(QuestionVariant.generated_at.desc(), QuestionVariant.id.desc())
    return [_variant_read(row) for row in db.scalars(query)]


def generate_question_variants(
    db: Session, point_id: int, connector: LlmConnector, count: int
) -> list[QuestionVariantRead]:
    if not GENERATION_SLOT.acquire(blocking=False):
        raise ConflictError("已有变式题正在生成，请稍后再试。")
    try:
        return _generate_question_variants(db, point_id, connector, count)
    finally:
        GENERATION_SLOT.release()


def _generate_question_variants(
    db: Session, point_id: int, connector: LlmConnector, count: int
) -> list[QuestionVariantRead]:
    point = _active_point(db, point_id)
    existing_questions = [item["question"] for item in (point.quiz_items or [])]
    point_name, summary, key_points = point.name, point.summary, point.key_points
    # Avoid holding a database transaction during a remote model call.
    db.rollback()
    content = connector.generate_question_variants(
        point_name=point_name, summary=summary, key_points=key_points,
        existing_questions=existing_questions, count=count,
    )
    point = _active_point(db, point_id)
    now = datetime.now(UTC)
    for pending in db.scalars(
        select(QuestionVariant).where(
            QuestionVariant.knowledge_point_id == point_id, QuestionVariant.status == "pending"
        )
    ):
        db.delete(pending)
    rows = [
        QuestionVariant(
            knowledge_point_id=point_id, question=item.question, answer=item.answer,
            status="pending", model=connector.model_name,
            prompt_version=QUESTION_VARIANTS_PROMPT_VERSION, generated_at=now,
        )
        for item in content.variants
    ]
    db.add_all(rows)
    db.commit()
    return [_variant_read(row) for row in rows]


def _reviewed_variant(db: Session, variant_id: int) -> QuestionVariant:
    row = db.scalar(select(QuestionVariant).where(QuestionVariant.id == variant_id).with_for_update())
    if row is None:
        raise NotFoundError("变式题不存在。")
    if row.status != "pending":
        raise ConflictError("这道变式题已处理过。")
    return row


def approve_variant(db: Session, variant_id: int) -> QuestionVariantRead:
    row = _reviewed_variant(db, variant_id)
    point = db.scalar(
        select(KnowledgePoint).where(KnowledgePoint.id == row.knowledge_point_id).with_for_update()
    )
    if point is None or not point.is_active:
        raise NotFoundError("知识点不存在。")
    point.quiz_items = [*(point.quiz_items or []), {"question": row.question, "answer": row.answer}]
    row.status = "approved"
    row.reviewed_at = datetime.now(UTC)
    db.commit()
    return _variant_read(row)


def reject_variant(db: Session, variant_id: int) -> QuestionVariantRead:
    row = _reviewed_variant(db, variant_id)
    row.status = "rejected"
    row.reviewed_at = datetime.now(UTC)
    db.commit()
    return _variant_read(row)
