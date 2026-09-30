import hashlib
import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.config import Settings, get_settings
from app.core.errors import (
    ConnectorNotConfiguredError,
    InvalidSourceUrlError,
    UpstreamInvalidResponseError,
    UpstreamUnavailableError,
)
from app.models import FeedSource


@dataclass(frozen=True)
class FeedEntry:
    external_id: str
    title: str
    content: str
    created_at: datetime
    source_url: str | None
    author: str | None


def validate_public_http_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidSourceUrlError("来源地址必须是完整的 http/https URL。")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise InvalidSourceUrlError("来源地址不能指向本机或私有网络。")
    try:
        addresses = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise UpstreamUnavailableError("无法解析订阅源地址。") from exc
    if not addresses:
        raise UpstreamUnavailableError("无法解析订阅源地址。")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise InvalidSourceUrlError("来源地址不能指向本机或私有网络。")
    return url


def _clean_html(value: str) -> str:
    if "<" not in value:
        plain = html.unescape(value)
        lines = [re.sub(r"\s+", " ", line).strip() for line in plain.splitlines()]
        return "\n".join(line for line in lines if line).strip()
    soup = BeautifulSoup(value or "", "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    lines = [re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _entry_value(entry: object, key: str, default: object = "") -> object:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _entry_content(entry: object) -> str:
    content = _entry_value(entry, "content", [])
    if isinstance(content, list) and content:
        first = content[0]
        value = _entry_value(first, "value", "")
        if isinstance(value, str):
            return _clean_html(value)
    for key in ("summary", "description"):
        value = _entry_value(entry, key, "")
        if isinstance(value, str) and value:
            return _clean_html(value)
    return ""


def _entry_date(entry: object) -> datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = _entry_value(entry, key, None)
        if isinstance(value, struct_time):
            return datetime(*value[:6], tzinfo=UTC)
    return datetime.now(UTC)


def parse_feed_document(data: bytes, max_items: int) -> list[FeedEntry]:
    parsed = feedparser.parse(data)
    if not parsed.entries:
        raise UpstreamInvalidResponseError("订阅源没有返回可识别的 RSS/Atom 条目。")

    results: list[FeedEntry] = []
    seen: set[str] = set()
    for raw_entry in parsed.entries[:max_items]:
        title_value = _entry_value(raw_entry, "title", "")
        title = _clean_html(title_value) if isinstance(title_value, str) else ""
        title = (title or "未命名资料")[:200]
        content = _entry_content(raw_entry)[:10000]
        link_value = _entry_value(raw_entry, "link", "")
        source_url = None
        if isinstance(link_value, str):
            candidate = link_value.strip()
            if urlsplit(candidate).scheme in {"http", "https"}:
                source_url = candidate[:2048]
        identifier_value = _entry_value(raw_entry, "id", "")
        identifier = identifier_value.strip() if isinstance(identifier_value, str) else ""
        if not identifier:
            identifier = source_url or ""
        if not identifier:
            seed = f"{title}\n{_entry_date(raw_entry).isoformat()}\n{content}"
            identifier = "hash:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        if len(identifier) > 255:
            identifier = "hash:" + hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        if identifier in seen:
            continue
        seen.add(identifier)
        author_value = _entry_value(raw_entry, "author", "")
        author = author_value.strip()[:200] if isinstance(author_value, str) else ""
        results.append(
            FeedEntry(
                external_id=identifier,
                title=title,
                content=content,
                created_at=_entry_date(raw_entry),
                source_url=source_url,
                author=author or None,
            )
        )
    return results


class FeedConnector:
    def __init__(
        self, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    def _source_url(self, source: FeedSource) -> tuple[str, str | None]:
        if source.source_type == "rsshub":
            if not self.settings.rsshub_base_url:
                raise ConnectorNotConfiguredError("RSSHub 连接器尚未配置。")
            base = self.settings.rsshub_base_url.rstrip("/")
            return f"{base}{source.endpoint}", urlsplit(base).hostname
        return source.endpoint, None

    def _read_response(self, url: str, trusted_host: str | None) -> bytes:
        current_url = url
        try:
            with httpx.Client(
                timeout=self.settings.feed_fetch_timeout_seconds,
                transport=self.transport,
            ) as client:
                for _ in range(6):
                    hostname = urlsplit(current_url).hostname
                    if not trusted_host or hostname != trusted_host:
                        validate_public_http_url(current_url)
                    with client.stream(
                        "GET",
                        current_url,
                        headers={"User-Agent": "KnowledgeReview/0.2 (+feed sync)"},
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise UpstreamInvalidResponseError(
                                    "订阅源返回了没有目标地址的重定向。"
                                )
                            current_url = urljoin(current_url, location)
                            continue
                        response.raise_for_status()
                        chunks: list[bytes] = []
                        size = 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > self.settings.feed_max_bytes:
                                raise UpstreamInvalidResponseError("订阅源响应体超过允许大小。")
                            chunks.append(chunk)
                        return b"".join(chunks)
                raise UpstreamInvalidResponseError("订阅源重定向次数过多。")
        except (InvalidSourceUrlError, UpstreamInvalidResponseError):
            raise
        except (httpx.HTTPError, OSError) as exc:
            raise UpstreamUnavailableError("无法连接订阅源，请稍后重试。") from exc

    def fetch_entries(self, source: FeedSource) -> list[FeedEntry]:
        url, trusted_host = self._source_url(source)
        return parse_feed_document(
            self._read_response(url, trusted_host),
            self.settings.feed_max_items,
        )


def get_feed_connector() -> FeedConnector:
    return FeedConnector(get_settings())
