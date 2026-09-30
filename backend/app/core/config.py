from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Knowledge Review API"
    database_url: str = "postgresql+psycopg://knowledge_review:change-me@localhost:5432/knowledge_review"
    cors_origins: str = "http://localhost:3000"
    notebook_api_url: str = ""
    notebook_api_token: SecretStr = SecretStr("")
    notebook_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    rsshub_base_url: str = ""
    crawl4ai_api_url: str = ""
    crawl4ai_api_token: SecretStr = SecretStr("")
    crawl4ai_timeout_seconds: float = Field(default=45.0, gt=0, le=180)
    feed_fetch_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    feed_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    feed_max_items: int = Field(default=30, ge=1, le=100)
    feed_max_crawl_items: int = Field(default=5, ge=0, le=30)
    feed_auto_crawl_threshold: int = Field(default=280, ge=0, le=5000)
    embedding_api_url: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_model: str = "text-embedding-3-small"
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    relevance_threshold: float = Field(default=0.6, ge=0, le=1)
    relevance_batch_size: int = Field(default=20, ge=1, le=100)
    llm_api_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=90.0, gt=0, le=300)
    llm_max_source_chars: int = Field(default=12000, ge=1000, le=50000)
    llm_max_output_tokens: int = Field(default=2500, ge=500, le=8000)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
