"""Release smoke in a newly created, isolated PostgreSQL database, then remove it.

Run inside the new backend image. Only the generated verification database is written.
No production rows or remote LLM are used.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

production_url = make_url(get_settings().database_url)
verification_name = "knowledge_review_verify_" + uuid4().hex[:12]
assert re.fullmatch(r"knowledge_review_verify_[0-9a-f]{12}", verification_name)
assert verification_name != production_url.database
admin = create_engine(production_url, isolation_level="AUTOCOMMIT")
created = False
app_engine = None
try:
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{verification_name}"'))
    created = True
    os.environ["DATABASE_URL"] = production_url.set(database=verification_name).render_as_string(hide_password=False)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    command.check(Config("alembic.ini"))

    from app.db.database import SessionLocal, engine as app_engine
    from app.models import Category, Topic, SourceDocument
    from app.schemas.analysis import ErrorAnalysisContent, QuestionVariantsContent
    from app.schemas.knowledge_draft import DraftContent, KnowledgeDraftReview, QuizItem
    from app.schemas.review import ReviewStart, ReviewAnswer
    from app.services import analysis, knowledge_drafts as drafts, knowledge_structure, reviews

    class FixtureLlm:
        model_name = "isolated-release-verification"

        def generate_draft(self, **_):
            return DraftContent(title="Verification knowledge", summary="A local test summary.",
                                difficulty="beginner", key_points=["A test point"],
                                quiz_items=[{"question": "Test question?", "answer": "Test answer."}])

        def classify_error(self, **_):
            return ErrorAnalysisContent(error_type="concept_confusion", explanation="Verification explanation.",
                                        suggestion="Verification suggestion.")

        def generate_question_variants(self, *, count, **_):
            return QuestionVariantsContent(variants=[
                QuizItem(question=f"Variant question {i}?", answer=f"Variant answer {i}.") for i in range(count)
            ])

    with SessionLocal() as db:
        category = Category(name="Verification", slug="verification", sort_order=0)
        db.add(category)
        db.flush()
        topic = Topic(category_id=category.id, name="Verification", slug="verification", sort_order=0)
        db.add(topic)
        source = SourceDocument(provider="verification", external_id="verification", title="Test source",
                                content="Test source content.", content_hash="b" * 64, status="pending",
                                source_created_at=datetime.now(UTC), last_seen_at=datetime.now(UTC))
        db.add(source)
        db.commit()
        draft = drafts.generate_draft(db, source_document_id=source.id, topic_id=topic.id, connector=FixtureLlm())
        repeat = drafts.generate_draft(db, source_document_id=source.id, topic_id=topic.id, connector=FixtureLlm())
        assert repeat.generation_count == 1
        payload = KnowledgeDraftReview.model_validate(draft.model_dump() | {"expected_revision": draft.revision})
        approved = drafts.approve_draft(db, draft.id, payload)
        assert approved.status == "approved"
        point_id = approved.knowledge_point_id

    def start():
        with SessionLocal() as db:
            return reviews.start_session(db, ReviewStart())

    with ThreadPoolExecutor(max_workers=2) as executor:
        sessions = list(executor.map(lambda _: start(), range(2)))
    assert sessions[0].id == sessions[1].id
    item_id = sessions[0].items[0].id
    assert sessions[0].items[0].standard_answer is None
    with SessionLocal() as db:
        reviews.reveal(db, item_id, "My answer.")

    def answer():
        with SessionLocal() as db:
            return reviews.answer(db, item_id, ReviewAnswer(user_answer="My answer.", rating="good"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        sessions = list(executor.map(lambda _: answer(), range(2)))
    assert all(session.status == "completed" for session in sessions)
    with SessionLocal() as db:
        stats = reviews.overview(db)
        assert stats.due_count == 0 and stats.reviewed_today == 1
        assert stats.points[0].knowledge_point_id == point_id and stats.points[0].review_count == 1
        assert stats.recent_sessions[0].question_count == 1
        weak_overview = analysis.overview(db)
        assert weak_overview.mastery_distribution.get("2") == 1  # single "good" rating advances L1 -> L2
        wrong_session = reviews.start_session(db, ReviewStart(knowledge_point_id=point_id))
        reviews.reveal(db, wrong_session.items[0].id, "Wrong answer.")
        reviews.answer(db, wrong_session.items[0].id, ReviewAnswer(user_answer="Wrong answer.", rating="again"))
        error_row = analysis.generate_error_analysis(db, point_id, FixtureLlm())
        assert error_row.error_type == "concept_confusion"
        assert analysis.get_error_analysis(db, point_id).id == error_row.id
        new_variants = analysis.generate_question_variants(db, point_id, FixtureLlm(), 2)
        assert len(new_variants) == 2
        approved_variant = analysis.approve_variant(db, new_variants[0].id)
        assert approved_variant.status == "approved"
        analysis.reject_variant(db, new_variants[1].id)
        grown_point = knowledge_structure.get_knowledge_point(db, point_id)
        assert len(grown_point.quiz_items) == 2  # the original question plus the approved variant
        knowledge_structure.delete_knowledge_point(db, point_id)
        db.expire_all()
        assert db.get(SourceDocument, source.id) is not None
        assert drafts.read_draft(db, draft.id).knowledge_point_id is None
        history = reviews.read_session(reviews.get_session(db, sessions[0].id))
        assert history.items[0].knowledge_point_id is None
        assert history.items[0].standard_answer == "Test answer."
    from app.core.errors import ConflictError
    from app.schemas.source_document import SourceContentApply
    from app.services import source_content, source_ingestion

    original_entry = source_ingestion.SourceEntry(external_id="preview-check", title="RSS excerpt", content="An excerpt [...]", created_at=datetime.now(UTC), source_url="https://example.com/article")
    with SessionLocal() as db:
        source_ingestion.upsert_source_entries(db, [original_entry], provider="feed:verification")
        db.commit()
        content_source = db.query(SourceDocument).filter_by(provider="feed:verification").one()
        content_source_id = content_source.id
        content_draft = drafts.generate_draft(db, source_document_id=content_source_id, topic_id=topic.id, connector=FixtureLlm())

    def supplement(body):
        with SessionLocal() as db:
            try:
                source_content.apply_content(db, content_source_id, SourceContentApply(expected_revision=1, content=body))
                return "applied"
            except ConflictError:
                db.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(supplement, ["First manual supplement", "Second manual supplement"]))
    assert sorted(outcomes) == ["applied", "conflict"]
    with SessionLocal() as db:
        supplemented = source_ingestion.read_source_document(db, content_source_id)
        assert supplemented.content_revision == 2 and supplemented.content_origin == "supplement"
        assert drafts.read_draft(db, content_draft.id).status == "stale"
        assert source_content.collected_content(db, content_source_id).content == original_entry.content
        result = source_ingestion.upsert_source_entries(db, [original_entry], provider="feed:verification")
        db.commit()
        assert result.unchanged == 1
        assert source_ingestion.read_source_document(db, content_source_id).content == supplemented.content
        restored = source_content.restore_content(db, content_source_id, 2)
        assert restored.content == original_entry.content and restored.content_revision == 3
    print("PASS: PostgreSQL migrations, concurrent content CAS, RSS supplement protection, draft approval, concurrent reviews, idempotent answers, error-analysis/question-variant generation and approval, and provenance-safe deletion")
finally:
    if app_engine is not None:
        app_engine.dispose()
    if created:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{verification_name}"'))
        print("Removed only the temporary verification database; production data unchanged")
    admin.dispose()
