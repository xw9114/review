from dataclasses import replace
import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import InvalidSourceUrlError, UpstreamInvalidResponseError, UpstreamUnavailableError
from app.integrations.article import article_html, fetch_article_html, public_address
from app.integrations.crawl4ai import Crawl4AIConnector, get_crawl4ai_connector
from app.integrations.feed import get_feed_connector
from app.integrations.llm import LlmConnector, get_llm_connector
from app.main import app
from app.models import SourceDocument
from tests.conftest import TestingSessionLocal
from app.services.content_quality import content_warnings
from tests.test_feed_sources_api import FakeFeedConnector, _create_feed
from tests.test_knowledge_drafts_api import FakeLlmConnector, review_payload


class ArticleCrawler:
    configured = True

    def __init__(self):
        self.calls = 0
        self.before_return = lambda: None

    def clean_article(self, url):
        assert url == "https://example.com/one"
        self.calls += 1
        self.before_return()
        return "# Adam 正文\n\n" + "更详细的梯度与动量说明。" * 100


def setup_feed(client):
    feed = FakeFeedConnector()
    feed.entries = [replace(feed.entries[0], content="这是 RSS 摘要。 [...]")]
    crawler = ArticleCrawler()
    llm = FakeLlmConnector()
    app.dependency_overrides[get_feed_connector] = lambda: feed
    app.dependency_overrides[get_crawl4ai_connector] = lambda: crawler
    app.dependency_overrides[get_llm_connector] = lambda: llm
    subscription = _create_feed(client, cleaning_mode="feed")
    sync_url = f"/api/v1/feed-sources/{subscription['id']}/sync"
    assert client.post(sync_url).status_code == 200
    source = client.get("/api/v1/source-documents").json()[0]
    category = client.post("/api/v1/categories", json={"name": "深度学习"}).json()
    topic = client.post("/api/v1/topics", json={"category_id": category["id"], "name": "Optimizer"}).json()
    return feed, crawler, llm, source, topic, sync_url


def test_preview_apply_preserves_rss_and_stales_without_overwriting_draft(client):
    _, crawler, llm, source, topic, sync_url = setup_feed(client)
    url = f"/api/v1/source-documents/{source['id']}"
    draft_url = url + "/draft/generate"
    with TestingSessionLocal() as db:
        cached = db.get(SourceDocument, source["id"])
        cached.embedding, cached.embedding_model, cached.embedding_input_hash = [1.0], "old-model", "old-input"
        cached.relevance_score, cached.relevance_passed, cached.processing_status = 0.9, True, "scored"
        db.commit()
    source = client.get(url).json()
    draft = client.post(draft_url, json={"topic_id": topic["id"]}).json()
    assert source["can_supplement"] and source["content_warnings"]
    preview = client.post(url + "/content-preview", json={"expected_revision": 1})
    assert preview.status_code == 200, preview.text
    candidate = preview.json()
    assert crawler.calls == 1 and len(llm.calls) == 1
    assert candidate["content_chars"] > source["content_chars"]
    assert client.get(url).json() == source  # Preview causes no DB writes.
    applied = client.patch(url + "/content", json={"content": candidate["content"], "expected_revision": 1})
    assert applied.status_code == 200, applied.text
    content = applied.json()
    assert content["content_origin"] == "supplement" and content["content_revision"] == 2
    assert content["processing_status"] == "unscored"
    assert content["relevance_score"] is None and content["relevance_passed"] is None
    with TestingSessionLocal() as db:
        cached = db.get(SourceDocument, source["id"])
        assert cached.embedding is None and cached.embedding_model is None and cached.embedding_input_hash is None
    assert client.get(url + "/content-collected").json()["content"] == source["content"]
    stale = client.get(f"/api/v1/knowledge-drafts/{draft['id']}").json()
    assert stale["status"] == "stale"
    assert stale["summary"] == draft["summary"] and stale["generation_count"] == 1
    assert client.post(f"/api/v1/knowledge-drafts/{draft['id']}/approve", json=review_payload(stale)).status_code == 409
    reopened = client.post(draft_url, json={"topic_id": topic["id"]}).json()
    assert reopened["status"] == "stale" and len(llm.calls) == 1
    assert client.post(sync_url).json()["unchanged"] == 1
    assert client.get(url).json()["content"] == candidate["content"]
    regenerated = client.post(draft_url, json={"topic_id": topic["id"], "regenerate": True, "expected_revision": stale["revision"]}).json()
    assert regenerated["generation_count"] == 2
    assert llm.calls[-1]["source_content"] == candidate["content"]
    assert client.get("/api/v1/knowledge-points").json() == []


def test_upstream_changes_do_not_overwrite_supplement_and_can_restore_latest(client):
    feed, _, _, source, topic, sync_url = setup_feed(client)
    url = f"/api/v1/source-documents/{source['id']}"
    first = client.patch(url + "/content", json={"content": "人工确认的正文", "expected_revision": 1}).json()
    same = client.patch(url + "/content", json={"content": "人工确认的正文", "expected_revision": 2}).json()
    assert same["content_revision"] == first["content_revision"]
    draft = client.post(url + "/draft/generate", json={"topic_id": topic["id"]}).json()
    feed.entries = [replace(feed.entries[0], title="新版标题", content="新 RSS 摘要。")]
    assert client.post(sync_url).json()["updated"] == 1
    kept = client.get(url).json()
    assert kept["content"] == first["content"] and kept["title"] == source["title"]
    assert kept["collected_changed"] and kept["content_revision"] == 3
    assert client.get(f"/api/v1/knowledge-drafts/{draft['id']}").json()["status"] == "draft"
    assert client.patch(url + "/content", json={"content": "不应覆盖", "expected_revision": 2}).status_code == 409
    assert client.post(url + "/content-restore", json={"expected_revision": 2}).status_code == 409
    restored = client.post(url + "/content-restore", json={"expected_revision": 3}).json()
    assert restored["content"] == "新 RSS 摘要。" and restored["title"] == "新版标题"
    assert restored["content_origin"] == "collected" and not restored["collected_changed"]
    assert client.post(sync_url).json()["unchanged"] == 1


def test_only_one_preview_runs_at_a_time(client):
    _, crawler, _, source, _, _ = setup_feed(client)
    url = f"/api/v1/source-documents/{source['id']}/content-preview"
    nested = []
    crawler.before_return = lambda: nested.append(client.post(url, json={"expected_revision": 1}).status_code)
    assert client.post(url, json={"expected_revision": 1}).status_code == 200
    assert nested == [409] and crawler.calls == 1


def test_crawl_failure_and_changes_during_preview_are_safe(client):
    _, crawler, _, source, _, _ = setup_feed(client)
    url = f"/api/v1/source-documents/{source['id']}"

    def fail():
        raise UpstreamUnavailableError("抓取失败")

    crawler.before_return = fail
    assert client.post(url + "/content-preview", json={"expected_revision": 1}).status_code == 502
    assert client.get(url).json() == source
    crawler.before_return = lambda: client.patch(url + "/content", json={"content": "另一页保存的内容", "expected_revision": 1})
    assert client.post(url + "/content-preview", json={"expected_revision": 1}).status_code == 409
    assert client.get(url).json()["content"] == "另一页保存的内容"
    crawler.before_return = lambda: None
    assert client.post(url + "/content-preview", json={"expected_revision": 2}).status_code == 200


def test_content_validation_limits_and_pending_only(client):
    _, _, _, source, topic, _ = setup_feed(client)
    url = f"/api/v1/source-documents/{source['id']}"
    for payload in ({"content": " "}, {"content": "正文", "expected_revision": 0}, {"content": " " * 20, "expected_revision": 1}, {"content": "x" * 50001, "expected_revision": 1}):
        assert client.patch(url + "/content", json=payload).status_code == 422
    long = client.patch(url + "/content", json={"content": "x" * 13000, "expected_revision": 1}).json()
    assert long["ai_input_truncated"] and long["ai_input_chars"] == 12000 and long["content_chars"] == 13000
    assert client.post(url + "/accept", json={"topic_id": topic["id"], "name": "人工入库"}).status_code == 200
    assert not client.get(url).json()["can_supplement"]
    assert client.patch(url + "/content", json={"content": "新内容", "expected_revision": 2}).status_code == 409
    assert client.post(url + "/content-preview", json={"expected_revision": 2}).status_code == 409
    assert client.get(url + "/content-collected").status_code == 200


def test_apply_and_restore_during_llm_cannot_accept_aba_source(client):
    _, _, llm, source, topic, _ = setup_feed(client)
    url = f"/api/v1/source-documents/{source['id']}"
    original_generate = llm.generate_draft

    def change_and_restore(**kwargs):
        assert client.patch(url + "/content", json={"content": "中途变更", "expected_revision": 1}).status_code == 200
        assert client.post(url + "/content-restore", json={"expected_revision": 2}).status_code == 200
        return original_generate(**kwargs)

    llm.generate_draft = change_and_restore
    assert client.post(url + "/draft/generate", json={"topic_id": topic["id"]}).status_code == 409
    assert client.get("/api/v1/knowledge-drafts").json() == []


@pytest.fixture
def public_dns(monkeypatch):
    def resolve(host, port, **_):
        ip = "127.0.0.1" if host in {"private.example", "127.0.0.1"} else "93.184.216.34"
        return [(2, 1, 6, "", (ip, port))]
    monkeypatch.setattr("app.integrations.article.socket.getaddrinfo", resolve)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://localhost/", "https://user:password@example.com/", "http://example.com:8000/", "http://example.com:bad/", "http://private.example/"])
def test_article_blocks_non_public_urls(public_dns, url):
    with pytest.raises(InvalidSourceUrlError):
        public_address(url)


def test_article_pins_dns_and_revalidates_redirects(public_dns):
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        return httpx.Response(302, headers={"location": "http://private.example/secret"})

    with pytest.raises(InvalidSourceUrlError):
        fetch_article_html("https://example.com/a", transport=httpx.MockTransport(respond))
    assert len(calls) == 1


@pytest.mark.parametrize("headers,content,error", [
    ({"content-type": "application/pdf"}, b"pdf", UpstreamInvalidResponseError),
    ({"content-type": "text/html"}, b"x" * (2 * 1024 * 1024 + 1), UpstreamInvalidResponseError),
    ({"content-type": "text/html", "content-encoding": "identity"}, b"<h1>OK</h1>", None),
], ids=["non-html", "oversized", "html"])
def test_article_limits_and_media_types(public_dns, headers, content, error):
    transport = httpx.MockTransport(lambda _: httpx.Response(200, headers=headers, content=content))
    if error:
        with pytest.raises(error):
            fetch_article_html("https://example.com/one", transport=transport)
    else:
        assert fetch_article_html("https://example.com/one", transport=transport) == (content, "https://example.com/one")


def test_article_sanitizes_and_preserves_tex():
    raw = ("<html><nav>menu</nav><article onclick='bad()'><p>" + "正文内容。" * 40 + "</p><script type='math/tex; mode=display'>x^2</script><script>bad()</script><iframe src='http://127.0.0.1'></iframe><img src='http://private/'><a href='/next'>next</a></article><div id='comments'>comment</div></html>")
    cleaned = article_html(raw.encode(), "https://example.com/a")
    assert "$$x^2$$" in cleaned and 'href="https://example.com/next"' in cleaned
    for bad in ("onclick", "iframe", "<script", "<img", "comment", "menu"):
        assert bad not in cleaned


def test_crawler_uses_inert_html_and_does_not_silently_truncate(monkeypatch):
    html = ("<article>" + "正文内容。" * 80 + "</article>").encode()
    monkeypatch.setattr("app.integrations.article.fetch_article_html", lambda _: (html, "https://example.com/a"))
    size = 12000

    def respond(request):
        payload = json.loads(request.content)
        assert payload["urls"][0].startswith("raw:")
        # Crawl4AI 0.9.2 REST forbids these fields even if set to False.
        assert "process_in_browser" not in payload["crawler_config"]["params"]
        assert "base_url" not in payload["crawler_config"]["params"]
        return httpx.Response(200, json={"results": [{"success": True, "markdown": "文" * size}]})

    crawler = Crawl4AIConnector(Settings(crawl4ai_api_url="http://cleaner:11235"), httpx.MockTransport(respond))
    assert len(crawler.clean_article("https://example.com/a")) == 12000
    size = 50001
    with pytest.raises(UpstreamInvalidResponseError):
        crawler.clean_article("https://example.com/a")


def test_quality_hints_and_model_input_budget():
    assert any("疑似摘要" in item for item in content_warnings("一些说明 [...]"))
    assert content_warnings("完整的短说明", collected=False) == []
    seen = []
    output = FakeLlmConnector().generate_draft().model_dump_json()

    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": output}}]})

    llm = LlmConnector(Settings(llm_api_url="https://llm.example/v1", llm_model="test", llm_max_source_chars=1000), httpx.MockTransport(respond))
    llm.generate_draft(source_title="Title", source_content="a" * 1100, category_name="Category", topic_name="Topic", topic_description=None)
    payload = json.loads(seen[0]["messages"][1]["content"])
    assert payload["source_total_chars"] == 1100 and payload["source_truncated"]
    assert len(payload["source_content"]) == 1000


@pytest.mark.parametrize("status", [401, 403])
def test_article_reports_access_restriction_without_retry(public_dns, status):
    calls = []

    def denied(request):
        calls.append(request)
        return httpx.Response(status)

    with pytest.raises(UpstreamUnavailableError, match=f"HTTP {status}"):
        fetch_article_html("https://example.com/article", transport=httpx.MockTransport(denied))
    assert len(calls) == 1
