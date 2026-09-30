import hashlib
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.errors import ConflictError, DomainError
from app.integrations.embedding import EmbeddingConnector
from app.models import Category, SourceDocument, Topic
from app.schemas.source_document import SourceDocumentRead, SourceScoreBatchResult
from app.services.source_ingestion import get_source_document, read_source_document


@dataclass(frozen=True)
class TopicProfile:
    topic: Topic
    category: Category
    text: str
    input_hash: str


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _topic_profiles(db: Session) -> list[TopicProfile]:
    topics = list(
        db.scalars(
            select(Topic)
            .options(joinedload(Topic.category))
            .order_by(Topic.sort_order, Topic.name)
        )
    )
    profiles: list[TopicProfile] = []
    for topic in topics:
        category = topic.category
        text = "\n".join(
            part
            for part in (
                f"领域：{category.name}",
                f"领域说明：{category.description or ''}",
                f"主题：{topic.name}",
                f"主题说明：{topic.description or ''}",
            )
            if part
        )
        profiles.append(
            TopicProfile(
                topic=topic,
                category=category,
                text=text,
                input_hash=_digest(text),
            )
        )
    return profiles


def _document_text(document: SourceDocument) -> str:
    return f"标题：{document.title}\n正文：{document.content[:8000]}"


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / denominator))


def _tokens(value: str) -> set[str]:
    lowered = value.casefold()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9+#._-]{1,}", lowered))
    for run in re.findall(r"[\u3400-\u9fff]{2,}", lowered):
        if len(run) <= 10:
            tokens.add(run)
        for width in (2, 3):
            tokens.update(run[index : index + width] for index in range(len(run) - width + 1))
    return tokens


def _keyword_score(document_text: str, profile: TopicProfile) -> tuple[float, list[str]]:
    document_tokens = _tokens(document_text)
    profile_tokens = _tokens(profile.text)
    overlap = document_tokens & profile_tokens
    coverage = len(overlap) / max(1, len(profile_tokens))
    score = coverage * 0.58
    lowered = document_text.casefold()
    matches: list[str] = []
    for label, bonus in (
        (profile.topic.name, 0.34),
        (profile.topic.description or "", 0.26),
        (profile.category.name, 0.14),
    ):
        normalized = label.strip().casefold()
        if len(normalized) >= 2 and normalized in lowered:
            score += bonus
            matches.append(label.strip())
    return min(1.0, score), list(dict.fromkeys(matches))[:3]


def _embedding_scores(
    document: SourceDocument,
    profiles: list[TopicProfile],
    connector: EmbeddingConnector,
) -> list[float]:
    document_text = _document_text(document)
    document_hash = _digest(document_text)
    document_vector = (
        document.embedding
        if document.embedding_model == connector.model_name
        and document.embedding_input_hash == document_hash
        else None
    )

    pending: list[tuple[str, int | None, str]] = []
    if document_vector is None:
        pending.append(("document", None, document_text))
    topic_vectors: dict[int, list[float]] = {}
    for profile in profiles:
        topic = profile.topic
        if (
            topic.embedding is not None
            and topic.embedding_model == connector.model_name
            and topic.embedding_input_hash == profile.input_hash
        ):
            topic_vectors[topic.id] = topic.embedding
        else:
            pending.append(("topic", topic.id, profile.text))

    if pending:
        vectors = connector.embed([item[2] for item in pending])
        for (kind, topic_id, _), vector in zip(pending, vectors, strict=True):
            if kind == "document":
                document_vector = vector
                document.embedding = vector
                document.embedding_model = connector.model_name
                document.embedding_input_hash = document_hash
            else:
                topic = next(profile.topic for profile in profiles if profile.topic.id == topic_id)
                profile = next(profile for profile in profiles if profile.topic.id == topic_id)
                topic.embedding = vector
                topic.embedding_model = connector.model_name
                topic.embedding_input_hash = profile.input_hash
                topic_vectors[topic.id] = vector

    if document_vector is None:
        raise RuntimeError("Embedding document vector was not produced.")
    return [_cosine(document_vector, topic_vectors[profile.topic.id]) for profile in profiles]


def _score_document(
    document: SourceDocument,
    profiles: list[TopicProfile],
    connector: EmbeddingConnector,
    settings: Settings,
) -> str:
    document_text = _document_text(document)
    matched_terms: list[str] = []
    if connector.is_configured:
        scores = _embedding_scores(document, profiles, connector)
        method = "embedding"
    else:
        keyword_results = [_keyword_score(document_text, profile) for profile in profiles]
        scores = [result[0] for result in keyword_results]
        method = "keyword"

    best_index = max(range(len(scores)), key=scores.__getitem__)
    best_profile = profiles[best_index]
    best_score = round(scores[best_index], 6)
    if method == "keyword":
        matched_terms = keyword_results[best_index][1]

    passed = best_score >= settings.relevance_threshold
    document.relevance_score = best_score
    document.relevance_passed = passed
    document.suggested_topic_id = best_profile.topic.id
    document.relevance_method = method
    document.processing_status = "scored"
    document.processed_at = datetime.now(UTC)
    destination = f"{best_profile.category.name} / {best_profile.topic.name}"
    if method == "embedding":
        document.relevance_reason = f"语义上与“{destination}”最接近。"
    elif matched_terms:
        document.relevance_reason = f"匹配到“{'、'.join(matched_terms)}”，推荐归入“{destination}”。"
    else:
        document.relevance_reason = f"关键词重合较少，当前最接近“{destination}”。"
    return method


def score_source_document(
    db: Session,
    source_document_id: int,
    connector: EmbeddingConnector,
    settings: Settings,
) -> SourceDocumentRead:
    document = get_source_document(db, source_document_id)
    if document.status == "stale":
        raise ConflictError("失效资料不能进行相关性分析。")
    profiles = _topic_profiles(db)
    if not profiles:
        raise ConflictError("请先创建至少一个主题，再分析资料。")
    _score_document(document, profiles, connector, settings)
    db.commit()
    return read_source_document(db, document.id)


def score_pending_sources(
    db: Session,
    connector: EmbeddingConnector,
    settings: Settings,
) -> SourceScoreBatchResult:
    profiles = _topic_profiles(db)
    if not profiles:
        raise ConflictError("请先创建至少一个主题，再分析资料。")
    document_ids = list(
        db.scalars(
            select(SourceDocument.id)
            .where(
                SourceDocument.status == "pending",
                SourceDocument.processing_status.in_(("unscored", "failed")),
            )
            .order_by(SourceDocument.source_created_at.desc(), SourceDocument.id.desc())
            .limit(settings.relevance_batch_size)
        )
    )
    embedding = keyword = scored = failed = passed = 0
    for document_id in document_ids:
        document = get_source_document(db, document_id)
        if document.status != "pending" or document.processing_status not in ("unscored", "failed"):
            db.rollback()
            continue
        content_revision = document.content_revision
        try:
            method = _score_document(document, profiles, connector, settings)
            db.commit()
            scored += 1
            passed += int(bool(document.relevance_passed))
            embedding += int(method == "embedding")
            keyword += int(method == "keyword")
        except DomainError as exc:
            db.rollback()
            failed_document = get_source_document(db, document_id)
            if failed_document.content_revision == content_revision:
                failed_document.processing_status = "failed"
                failed_document.relevance_reason = exc.message
                failed_document.processed_at = datetime.now(UTC)
                db.commit()
            failed += 1

    return SourceScoreBatchResult(
        requested=len(document_ids),
        scored=scored,
        failed=failed,
        embedding=embedding,
        keyword=keyword,
        passed=passed,
        threshold=settings.relevance_threshold,
    )
