import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import (
    ConnectorNotConfiguredError,
    UpstreamInvalidResponseError,
    UpstreamUnavailableError,
)
from app.integrations.feed import validate_public_http_url


def _markdown_from_result(result: dict[str, Any]) -> str:
    if result.get("success") is False:
        return ""
    markdown = result.get("markdown")
    if isinstance(markdown, str):
        return markdown.strip()
    if isinstance(markdown, dict):
        for key in ("fit_markdown", "raw_markdown", "markdown_with_citations"):
            value = markdown.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("fit_markdown", "raw_markdown"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_markdown(payload: dict[str, Any]) -> str:
    candidates: list[dict[str, Any]] = []
    results = payload.get("results")
    if isinstance(results, list):
        candidates.extend(item for item in results if isinstance(item, dict))
    result = payload.get("result")
    if isinstance(result, dict):
        candidates.append(result)
    candidates.append(payload)
    for candidate in candidates:
        markdown = _markdown_from_result(candidate)
        if markdown:
            return markdown
    raise UpstreamInvalidResponseError("Crawl4AI 没有返回可用正文。")


class Crawl4AIConnector:
    def __init__(
        self, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.settings.crawl4ai_api_url)

    def _headers(self) -> dict[str, str]:
        token = self.settings.crawl4ai_api_token.get_secret_value()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def clean(self, url: str) -> str:
        if not self.configured:
            raise ConnectorNotConfiguredError("Crawl4AI 连接器尚未配置。")
        validate_public_http_url(url)
        return self._crawl({"urls": [url]})[:10000]

    def clean_article(self, url: str) -> str:
        from app.integrations.article import article_html, fetch_article_html

        if not self.configured:
            raise ConnectorNotConfiguredError("Crawl4AI 尚未配置，可使用手动粘贴正文。")
        data, final_url = fetch_article_html(url)
        html = article_html(data, final_url)
        markdown = self._crawl({
            "urls": [f"raw:{html}"],
            "crawler_config": {"type": "CrawlerRunConfig", "params": {
                # raw: uses the server's default non-browser path. 0.9.2 REST
                # rejects process_in_browser even when explicitly set to False.
                "exclude_all_images": True, "verbose": False,
            }},
        })
        if len(markdown) > 50000:
            raise UpstreamInvalidResponseError("抽取结果超过 50,000 字符，未截断保存；请手动选取所需正文。")
        return markdown

    def _crawl(self, request_body: dict[str, Any]) -> str:
        if not self.configured:
            raise ConnectorNotConfiguredError("Crawl4AI 连接器尚未配置。")
        base = self.settings.crawl4ai_api_url.rstrip("/")
        deadline = time.monotonic() + self.settings.crawl4ai_timeout_seconds
        try:
            with httpx.Client(
                timeout=self.settings.crawl4ai_timeout_seconds,
                headers=self._headers(),
                transport=self.transport,
            ) as client:
                response = client.post(f"{base}/crawl", json=request_body)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise UpstreamInvalidResponseError("Crawl4AI 返回结构不正确。")
                task_id = payload.get("task_id")
                while task_id and not payload.get("results") and not payload.get("result"):
                    if time.monotonic() >= deadline:
                        raise UpstreamUnavailableError("Crawl4AI 清洗超时。")
                    time.sleep(1)
                    status = client.get(f"{base}/task/{task_id}")
                    status.raise_for_status()
                    payload = status.json()
                    if not isinstance(payload, dict):
                        raise UpstreamInvalidResponseError("Crawl4AI 返回结构不正确。")
                    if payload.get("status") == "failed":
                        raise UpstreamUnavailableError("Crawl4AI 无法清洗该页面。")
                return extract_markdown(payload)
        except (ConnectorNotConfiguredError, UpstreamInvalidResponseError, UpstreamUnavailableError):
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamUnavailableError("无法连接 Crawl4AI，请稍后重试。") from exc


def get_crawl4ai_connector() -> Crawl4AIConnector:
    return Crawl4AIConnector(get_settings())
