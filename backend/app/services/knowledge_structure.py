from typing import TypeVar

from slugify import slugify
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Category, KnowledgePoint, SourceDocument, Topic
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate
from app.schemas.topic import TopicCreate, TopicUpdate

ModelT = TypeVar("ModelT", Category, Topic, KnowledgePoint)


def _invalidate_relevance_scores(db: Session) -> None:
    db.execute(
        update(SourceDocument).values(
            relevance_score=None,
            relevance_passed=None,
            suggested_topic_id=None,
            relevance_method=None,
            relevance_reason=None,
            processing_status="unscored",
            processed_at=None,
        )
    )


def _commit(db: Session, entity: ModelT, conflict_message: str) -> ModelT:
    try:
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_message) from exc


def _normalized_slug(value: str | None, name: str) -> str:
    normalized = slugify(value or name)
    if not normalized:
        raise ConflictError("A non-empty slug is required for this name.")
    return normalized


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.sort_order, Category.name)))


def get_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    return category


def create_category(db: Session, payload: CategoryCreate) -> Category:
    category = Category(
        name=payload.name.strip(),
        slug=_normalized_slug(payload.slug, payload.name),
        description=payload.description,
        sort_order=payload.sort_order,
    )
    return _commit(db, category, "A category with this name or slug already exists.")


def update_category(db: Session, category_id: int, payload: CategoryUpdate) -> Category:
    category = get_category(db, category_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "slug" in changes:
        changes["slug"] = _normalized_slug(changes["slug"], changes.get("name", category.name))
    for field, value in changes.items():
        setattr(category, field, value)
    if {"name", "description"} & changes.keys():
        for topic in db.scalars(select(Topic).where(Topic.category_id == category.id)):
            topic.embedding = None
            topic.embedding_model = None
            topic.embedding_input_hash = None
        _invalidate_relevance_scores(db)
    return _commit(db, category, "A category with this name or slug already exists.")


def delete_category(db: Session, category_id: int) -> None:
    category = get_category(db, category_id)
    _invalidate_relevance_scores(db)
    db.delete(category)
    db.commit()


def list_topics(db: Session, category_id: int | None = None) -> list[Topic]:
    query = select(Topic)
    if category_id is not None:
        query = query.where(Topic.category_id == category_id)
    return list(db.scalars(query.order_by(Topic.sort_order, Topic.name)))


def get_topic(db: Session, topic_id: int) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("Topic not found.")
    return topic


def create_topic(db: Session, payload: TopicCreate) -> Topic:
    get_category(db, payload.category_id)
    topic = Topic(
        category_id=payload.category_id,
        name=payload.name.strip(),
        slug=_normalized_slug(payload.slug, payload.name),
        description=payload.description,
        sort_order=payload.sort_order,
    )
    _invalidate_relevance_scores(db)
    return _commit(db, topic, "A topic with this name or slug already exists in the category.")


def update_topic(db: Session, topic_id: int, payload: TopicUpdate) -> Topic:
    topic = get_topic(db, topic_id)
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        get_category(db, changes["category_id"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "slug" in changes:
        changes["slug"] = _normalized_slug(changes["slug"], changes.get("name", topic.name))
    for field, value in changes.items():
        setattr(topic, field, value)
    if {"category_id", "name", "description"} & changes.keys():
        topic.embedding = None
        topic.embedding_model = None
        topic.embedding_input_hash = None
        _invalidate_relevance_scores(db)
    return _commit(db, topic, "A topic with this name or slug already exists in the category.")


def delete_topic(db: Session, topic_id: int) -> None:
    topic = get_topic(db, topic_id)
    _invalidate_relevance_scores(db)
    db.delete(topic)
    db.commit()


def list_knowledge_points(db: Session, topic_id: int | None = None) -> list[KnowledgePoint]:
    query = select(KnowledgePoint)
    if topic_id is not None:
        query = query.where(KnowledgePoint.topic_id == topic_id)
    return list(db.scalars(query.order_by(KnowledgePoint.sort_order, KnowledgePoint.name)))


def get_knowledge_point(db: Session, knowledge_point_id: int) -> KnowledgePoint:
    knowledge_point = db.get(KnowledgePoint, knowledge_point_id)
    if knowledge_point is None:
        raise NotFoundError("Knowledge point not found.")
    return knowledge_point


def create_knowledge_point(db: Session, payload: KnowledgePointCreate) -> KnowledgePoint:
    get_topic(db, payload.topic_id)
    knowledge_point = KnowledgePoint(
        topic_id=payload.topic_id,
        name=payload.name.strip(),
        slug=_normalized_slug(payload.slug, payload.name),
        description=payload.description,
        summary=payload.summary,
        difficulty=payload.difficulty,
        key_points=payload.key_points,
        quiz_items=(
            [item.model_dump() for item in payload.quiz_items]
            if payload.quiz_items is not None
            else None
        ),
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    return _commit(
        db,
        knowledge_point,
        "A knowledge point with this name or slug already exists in the topic.",
    )


def update_knowledge_point(
    db: Session, knowledge_point_id: int, payload: KnowledgePointUpdate
) -> KnowledgePoint:
    knowledge_point = get_knowledge_point(db, knowledge_point_id)
    changes = payload.model_dump(exclude_unset=True)
    if "topic_id" in changes:
        get_topic(db, changes["topic_id"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "slug" in changes:
        changes["slug"] = _normalized_slug(
            changes["slug"], changes.get("name", knowledge_point.name)
        )
    for field, value in changes.items():
        setattr(knowledge_point, field, value)
    return _commit(
        db,
        knowledge_point,
        "A knowledge point with this name or slug already exists in the topic.",
    )


def delete_knowledge_point(db: Session, knowledge_point_id: int) -> None:
    knowledge_point = get_knowledge_point(db, knowledge_point_id)
    db.delete(knowledge_point)
    db.commit()
