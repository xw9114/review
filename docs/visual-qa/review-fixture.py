"""Local isolated API for browser QA; never connects to production or a real LLM."""
import os
import tempfile
from datetime import UTC, datetime

import uvicorn

fixture_dir = tempfile.TemporaryDirectory(prefix="review-browser-qa-")
os.environ["DATABASE_URL"] = "sqlite:///" + (fixture_dir.name + "/qa.sqlite3").replace("\\", "/")
os.environ["CORS_ORIGINS"] = "http://localhost:3001,http://127.0.0.1:3001"

from app.db.database import Base, engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Category, Topic, SourceDocument, FeedSource  # noqa: E402
from app.integrations.llm import get_llm_connector  # noqa: E402
from app.integrations.crawl4ai import get_crawl4ai_connector  # noqa: E402
from app.integrations.feed import FeedEntry, get_feed_connector  # noqa: E402
from app.schemas.knowledge_draft import DraftContent  # noqa: E402
from app.services.source_ingestion import SourceEntry, upsert_source_entries  # noqa: E402


class FixtureLlm:
    model_name = "local-qa-fixture"

    def generate_draft(self, **_):
        return DraftContent(
            title="Adam 优化器的核心机制",
            summary="Adam 用梯度的一阶和二阶矩估计自适应调整更新步长。",
            difficulty="intermediate", key_points=["一阶矩是梯度的移动平均。", "二阶矩是梯度平方的移动平均。"],
            quiz_items=[{"question": "Adam 的一阶矩是什么？", "answer": "梯度的指数移动平均。"},
                        {"question": "为什么需要偏差修正？", "answer": "零初始化的移动平均在训练初期偏向零。"}],
        )


Base.metadata.create_all(engine)
with SessionLocal() as db:
    category = Category(name="深度学习", slug="deep-learning", sort_order=0)
    db.add(category)
    db.flush()
    db.add(Topic(category_id=category.id, name="Optimizer", slug="optimizer", sort_order=0))
    if os.environ.get("SOURCE_SUPPLEMENT_QA") == "1":
        feed = FeedSource(name="测试 RSS", source_type="rss", endpoint="https://example.com/feed", cleaning_mode="feed", enabled=True)
        db.add(feed)
        db.flush()
        excerpt = "## Adam\n\n一阶矩 $m_t$ 记录梯度的指数移动平均。这是订阅摘要。\n\n[...]"
        upsert_source_entries(db, [SourceEntry(external_id="qa-adam", title="Adam 原文", content=excerpt, source_url="https://example.com/adam", created_at=datetime.now(UTC))], provider=f"feed:{feed.id}", feed_source_id=feed.id)

        class FixtureFeed:
            def fetch_entries(self, _):
                return [FeedEntry(external_id="qa-adam", title="Adam 原文", content=excerpt, source_url="https://example.com/adam", created_at=datetime.now(UTC), author=None)]

        class FixtureCrawler:
            configured = True

            def clean_article(self, _):
                return "## Adam 的矩估计\n\n" + ("一阶矩 $m_t$ 是梯度的移动平均；二阶矩缩放步长。\n\n$$m_t = \\beta_1 m_{t-1} + (1-\\beta_1)g_t$$\n\n需要在训练初期进行偏差修正。\n\n" * 8)

        app.dependency_overrides[get_feed_connector] = FixtureFeed
        app.dependency_overrides[get_crawl4ai_connector] = FixtureCrawler
    else:
        db.add(SourceDocument(provider="notebook", external_id="qa-adam", title="Adam 原文", content="## Adam\n\n一阶矩 $m_t$ 记录梯度的指数移动平均。\n\n二阶矩用于缩放更新步长，初始阶段需要偏差修正。", content_hash="a" * 64, status="pending", source_created_at=datetime.now(UTC), last_seen_at=datetime.now(UTC), processing_status="unscored"))
    db.commit()
app.dependency_overrides[get_llm_connector] = FixtureLlm

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
    finally:
        engine.dispose()
        fixture_dir.cleanup()
