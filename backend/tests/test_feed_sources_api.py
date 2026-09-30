from dataclasses import replace
from datetime import UTC, datetime
import warnings

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import InvalidSourceUrlError, UpstreamInvalidResponseError, UpstreamUnavailableError
from app.integrations.crawl4ai import extract_markdown, get_crawl4ai_connector
from app.integrations.feed import (
    FeedConnector,
    FeedEntry,
    get_feed_connector,
    parse_feed_document,
    validate_public_http_url,
)
from app.main import app
from app.models import FeedSource


class FakeFeedConnector:
    def __init__(self) -> None:
        self.entries = [
            FeedEntry(
                external_id="article-1",
                title="完整正文",
                content="足够长的正文" * 80,
                created_at=datetime(2026, 9, 22, tzinfo=UTC),
                source_url="https://example.com/one",
                author="作者甲",
            ),
            FeedEntry(
                external_id="article-2",
                title="短摘要",
                content="很短",
                created_at=datetime(2026, 9, 23, tzinfo=UTC),
                source_url="https://example.com/two",
                author=None,
            ),
        ]

    def fetch_entries(self, _: FeedSource) -> list[FeedEntry]:
        return self.entries


class FakeCrawler:
    configured = True

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.fail = False

    def clean(self, url: str) -> str:
        self.urls.append(url)
        if self.fail:
            raise UpstreamUnavailableError("crawler unavailable")
        return "# 清洗后的正文\n\n这是完整内容。"


def _create_feed(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "工程博客",
        "source_type": "rss",
        "endpoint": "https://example.com/feed.xml",
        "cleaning_mode": "auto",
        "enabled": True,
    }
    payload.update(overrides)
    response = client.post("/api/v1/feed-sources", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_feed_source_crud_and_validation(client: TestClient) -> None:
    created = _create_feed(client)
    assert created["last_sync_status"] == "never"
    assert client.post(
        "/api/v1/feed-sources",
        json={
            "name": "错误 RSSHub",
            "source_type": "rsshub",
            "endpoint": "https://rsshub.app/bilibili",
        },
    ).status_code == 422
    assert client.post(
        "/api/v1/feed-sources",
        json={
            "name": "私网地址",
            "source_type": "rss",
            "endpoint": "http://127.0.0.1/feed",
        },
    ).status_code == 422
    assert client.post(
        "/api/v1/feed-sources",
        json={
            "name": "工程博客",
            "source_type": "rss",
            "endpoint": "https://example.net/feed",
        },
    ).status_code == 409

    updated = client.patch(
        f"/api/v1/feed-sources/{created['id']}",
        json={"source_type": "rsshub", "endpoint": "/github/issue/DIYgod/RSSHub", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["source_type"] == "rsshub"
    assert updated.json()["enabled"] is False


def test_feed_sync_cleans_deduplicates_and_never_stales(client: TestClient) -> None:
    fake_feed = FakeFeedConnector()
    fake_crawler = FakeCrawler()
    app.dependency_overrides[get_feed_connector] = lambda: fake_feed
    app.dependency_overrides[get_crawl4ai_connector] = lambda: fake_crawler
    source = _create_feed(client)

    first = client.post(f"/api/v1/feed-sources/{source['id']}/sync")
    assert first.status_code == 200, first.text
    assert first.json() == {
        "feed_source_id": source["id"],
        "feed_source_name": "工程博客",
        "created": 2,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
        "cleaned": 1,
        "clean_failed": 0,
        "total": 2,
    }
    assert fake_crawler.urls == ["https://example.com/two"]

    documents = client.get("/api/v1/source-documents?status=pending").json()
    assert len(documents) == 2
    cleaned = next(item for item in documents if item["external_id"] == "article-2")
    assert cleaned["source_name"] == "工程博客"
    assert cleaned["source_url"] == "https://example.com/two"
    assert cleaned["content"].startswith("# 清洗后的正文")

    second = client.post(f"/api/v1/feed-sources/{source['id']}/sync").json()
    assert second["created"] == 0
    assert second["unchanged"] == 2

    fake_feed.entries = fake_feed.entries[:1]
    third = client.post(f"/api/v1/feed-sources/{source['id']}/sync").json()
    assert third["unchanged"] == 1
    assert len(client.get("/api/v1/source-documents?status=pending").json()) == 2

    fake_feed.entries = [replace(fake_feed.entries[0], content="已经更新的正文" * 80)]
    fourth = client.post(f"/api/v1/feed-sources/{source['id']}/sync").json()
    assert fourth["updated"] == 1


def test_forced_crawl_failure_skips_item(client: TestClient) -> None:
    fake_feed = FakeFeedConnector()
    fake_crawler = FakeCrawler()
    fake_crawler.fail = True
    app.dependency_overrides[get_feed_connector] = lambda: fake_feed
    app.dependency_overrides[get_crawl4ai_connector] = lambda: fake_crawler
    source = _create_feed(client, cleaning_mode="crawl4ai")

    result = client.post(f"/api/v1/feed-sources/{source['id']}/sync")
    assert result.status_code == 200
    assert result.json()["failed"] == 2
    assert result.json()["created"] == 0
    refreshed = client.get("/api/v1/feed-sources").json()[0]
    assert refreshed["last_sync_status"] == "partial"
    assert refreshed["last_failed"] == 2


def test_auto_mode_falls_back_when_crawler_fails(client: TestClient) -> None:
    fake_feed = FakeFeedConnector()
    fake_crawler = FakeCrawler()
    fake_crawler.fail = True
    app.dependency_overrides[get_feed_connector] = lambda: fake_feed
    app.dependency_overrides[get_crawl4ai_connector] = lambda: fake_crawler
    source = _create_feed(client)

    result = client.post(f"/api/v1/feed-sources/{source['id']}/sync").json()
    assert result["created"] == 2
    assert result["failed"] == 0
    assert result["clean_failed"] == 1
    documents = client.get("/api/v1/source-documents?status=pending").json()
    fallback = next(item for item in documents if item["external_id"] == "article-2")
    assert fallback["content"] == "很短"


def test_feed_parser_identifier_fallback_and_html_cleanup() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><title>Demo</title>
      <item><guid>stable-1</guid><title><![CDATA[<b>First</b>]]></title>
        <link>https://example.com/first</link><description><![CDATA[<p>Hello</p><script>bad()</script>]]></description>
        <author>Alice</author><pubDate>Tue, 22 Sep 2026 08:00:00 GMT</pubDate></item>
      <item><title>Fallback</title><description>Only content</description></item>
    </channel></rss>"""
    entries = parse_feed_document(xml, 30)
    assert [entry.title for entry in entries] == ["First", "Fallback"]
    assert entries[0].external_id == "stable-1"
    assert entries[0].content == "Hello"
    assert entries[1].external_id.startswith("hash:")
    with pytest.raises(UpstreamInvalidResponseError):
        parse_feed_document(b"not a feed", 30)


def test_feed_parser_accepts_url_shaped_plain_text_without_warning() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><title>Smoke</title>
      <item><title>https://example.com/article</title>
        <link>https://example.com/article</link>
        <description>plain &amp;amp; safe</description></item>
    </channel></rss>"""

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        entries = parse_feed_document(xml, 5)

    assert entries[0].title == "https://example.com/article"
    assert entries[0].content == "plain & safe"


def test_public_url_validation_blocks_private_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.integrations.feed.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 80))],
    )
    with pytest.raises(InvalidSourceUrlError):
        validate_public_http_url("http://example.com/feed")


def test_feed_connector_revalidates_redirect_and_limits_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
        address = "127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"
        return [(2, 1, 6, "", (address, port))]

    monkeypatch.setattr("app.integrations.feed.socket.getaddrinfo", resolve)
    source = FeedSource(
        name="Demo",
        source_type="rss",
        endpoint="https://example.com/feed",
        cleaning_mode="feed",
        enabled=True,
    )
    redirecting = FeedConnector(
        Settings(feed_max_bytes=1024),
        httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        ),
    )
    with pytest.raises(InvalidSourceUrlError):
        redirecting.fetch_entries(source)

    oversized = FeedConnector(
        Settings(feed_max_bytes=1024),
        httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 2048)),
    )
    with pytest.raises(UpstreamInvalidResponseError):
        oversized.fetch_entries(source)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"results": [{"success": True, "markdown": "result markdown"}]}, "result markdown"),
        ({"result": {"success": True, "markdown": {"fit_markdown": "fit"}}}, "fit"),
        ({"success": True, "raw_markdown": "raw"}, "raw"),
    ],
)
def test_extract_markdown_response_shapes(payload: dict[str, object], expected: str) -> None:
    assert extract_markdown(payload) == expected
