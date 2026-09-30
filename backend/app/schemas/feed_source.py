import ipaddress
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator

FeedSourceType = Literal["rss", "rsshub"]
CleaningMode = Literal["feed", "auto", "crawl4ai"]
FeedSyncStatus = Literal["never", "success", "partial", "failed"]


class FeedSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: FeedSourceType
    endpoint: str = Field(min_length=1, max_length=2048)
    cleaning_mode: CleaningMode = "auto"
    enabled: bool = True

    @model_validator(mode="after")
    def validate_endpoint(self) -> "FeedSourceCreate":
        self.name = self.name.strip()
        self.endpoint = self.endpoint.strip()
        if not self.name:
            raise ValueError("订阅源名称不能为空")
        if self.source_type == "rss":
            parsed = urlsplit(self.endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("RSS 地址必须是完整的 http/https URL")
            hostname = parsed.hostname.rstrip(".").lower()
            if parsed.username or parsed.password:
                raise ValueError("RSS 地址不能包含用户名或密码")
            if hostname == "localhost" or hostname.endswith(".localhost"):
                raise ValueError("RSS 地址不能指向本机或私有网络")
            try:
                literal_ip = ipaddress.ip_address(hostname)
            except ValueError:
                literal_ip = None
            if literal_ip is not None and (
                literal_ip.is_private
                or literal_ip.is_loopback
                or literal_ip.is_link_local
                or literal_ip.is_multicast
                or literal_ip.is_reserved
                or literal_ip.is_unspecified
            ):
                raise ValueError("RSS 地址不能指向本机或私有网络")
        elif not self.endpoint.startswith("/") or self.endpoint.startswith("//"):
            raise ValueError("RSSHub 路由必须以单个 / 开头")
        return self


class FeedSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    source_type: FeedSourceType | None = None
    endpoint: str | None = Field(default=None, min_length=1, max_length=2048)
    cleaning_mode: CleaningMode | None = None
    enabled: bool | None = None


class FeedSourceRead(BaseModel):
    id: int
    name: str
    source_type: FeedSourceType
    endpoint: str
    cleaning_mode: CleaningMode
    enabled: bool
    last_synced_at: datetime | None
    last_sync_status: FeedSyncStatus
    last_error: str | None
    last_created: int
    last_updated: int
    last_unchanged: int
    last_failed: int
    last_cleaned: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeedSyncResult(BaseModel):
    feed_source_id: int
    feed_source_name: str
    created: int
    updated: int
    unchanged: int
    failed: int
    cleaned: int
    clean_failed: int
    total: int


class FeedSyncBatchResult(BaseModel):
    sources: int
    succeeded: int
    failed_sources: int
    created: int
    updated: int
    unchanged: int
    failed: int
    cleaned: int
    clean_failed: int
    total: int
    results: list[FeedSyncResult]
