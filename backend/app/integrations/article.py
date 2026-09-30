"""Bounded, static public-page reads for an explicitly requested preview.

Resolve and validate every redirect, then connect to the validated IP while
retaining the original Host/SNI. The cleaner only receives inert HTML (raw:),
never an arbitrary URL to execute in its browser.
"""

import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.errors import InvalidSourceUrlError, UpstreamInvalidResponseError, UpstreamUnavailableError

MAX_PAGE_BYTES = 2 * 1024 * 1024


def public_address(url: str) -> tuple[httpx.URL, str]:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("invalid public URL")
        if parsed.port not in {None, 80, 443}:
            raise ValueError("unsupported port")
        target = httpx.URL(url).copy_with(fragment=None)
        hostname = target.host.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("local hostname")
        addresses = socket.getaddrinfo(hostname, target.port or (443 if target.scheme == "https" else 80), type=socket.SOCK_STREAM)
        ips = [ipaddress.ip_address(item[4][0]) for item in addresses]
        if not ips or any(not ip.is_global or ip.is_multicast for ip in ips):
            raise ValueError("non-public address")
        # Prefer IPv4 when available: small VPS installations may lack IPv6 egress.
        address = next((ip for ip in ips if ip.version == 4), ips[0])
        return target, str(address)
    except (ValueError, httpx.InvalidURL) as exc:
        raise InvalidSourceUrlError("原文地址必须是公开的 HTTP/HTTPS 网页，不能含账号、私网地址或非标准端口。") from exc
    except OSError as exc:
        raise UpstreamUnavailableError("无法解析原文地址，可稍后重试或手动粘贴正文。") from exc


def fetch_article_html(url: str, *, transport: httpx.BaseTransport | None = None) -> tuple[bytes, str]:
    deadline = time.monotonic() + 30
    current_url = url
    try:
        for _ in range(6):
            target, address = public_address(current_url)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise UpstreamUnavailableError("原文抓取超时，请重试或手动粘贴正文。")
            # Separate pools per hop avoid reusing a TLS session across hosts sharing an IP.
            with httpx.Client(timeout=min(15, remaining), transport=transport, trust_env=False, follow_redirects=False) as client:
                with client.stream(
                    "GET", target.copy_with(host=address),
                    headers={"Host": target.netloc.decode("ascii"), "User-Agent": "KnowledgeReview/0.3 (manual article preview)", "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "identity"},
                    extensions={"sni_hostname": target.host},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise UpstreamInvalidResponseError("原文重定向缺少目标地址。")
                        current_url = urljoin(str(target), location)
                        continue
                    response.raise_for_status()
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise UpstreamInvalidResponseError("原网页要求压缩响应，暂不自动读取；请手动粘贴正文。")
                    media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if media_type not in {"text/html", "application/xhtml+xml"}:
                        raise UpstreamInvalidResponseError("该地址不是 HTML 网页，请手动粘贴正文。")
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes(chunk_size=65536):
                        size += len(chunk)
                        if size > MAX_PAGE_BYTES:
                            raise UpstreamInvalidResponseError("原网页超过 2 MB，请手动粘贴所需正文。")
                        if time.monotonic() > deadline:
                            raise UpstreamUnavailableError("原文抓取超时，请手动粘贴正文。")
                        chunks.append(chunk)
                    return b"".join(chunks), str(target)
        raise UpstreamInvalidResponseError("原文重定向次数过多。")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {401, 403}:
            raise UpstreamUnavailableError(f"原站拒绝自动读取（HTTP {status}），请打开原文后手动粘贴正文。") from exc
        raise UpstreamUnavailableError(f"原站返回 HTTP {status}，请稍后重试或手动粘贴正文。") from exc
    except (httpx.HTTPError, OSError) as exc:
        raise UpstreamUnavailableError("无法读取原网页，可能需要登录或被网站限制；可手动粘贴正文。") from exc


def article_html(data: bytes, base_url: str) -> str:
    soup = BeautifulSoup(data, "html.parser")
    # MathJax stores some formulas in inert script elements; retain the TeX only.
    for node in soup.find_all("script"):
        if str(node.get("type", "")).startswith("math/tex"):
            display = "mode=display" in str(node.get("type"))
            delimiter = "$$" if display else "$"
            node.replace_with(f"\n{delimiter}{node.get_text()}{delimiter}\n")
    for node in soup(["script", "style", "noscript", "iframe", "object", "embed", "svg", "img", "video", "audio", "form", "nav", "footer", "aside", "meta", "link", "base"]):
        node.decompose()
    for node in soup.select("#comments, .comments, .comment-list, #comment-list, .post-nav, .share, .related-posts"):
        node.decompose()
    main = None
    for selector in ("[itemprop='articleBody']", ".entry-content", ".post-content", ".post_content", "#article-content", "article", "main"):
        candidate = soup.select_one(selector)
        if candidate and len(candidate.get_text(strip=True)) >= 100:
            main = candidate
            break
    main = main or soup.body or soup
    # No event attributes, resource attributes, or executable URLs survive.
    for node in [main, *main.find_all(True)]:
        href = node.get("href") if node.name == "a" else None
        node.attrs = {}
        if isinstance(href, str):
            absolute = urljoin(base_url, href)
            if urlsplit(absolute).scheme in {"http", "https"}:
                node["href"] = absolute
    if len(main.get_text(strip=True)) < 80:
        raise UpstreamInvalidResponseError("页面没有足够的可读正文，可能依赖登录或脚本；请手动粘贴。")
    return str(main)
