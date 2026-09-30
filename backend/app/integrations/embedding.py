import math

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import (
    ConnectorNotConfiguredError,
    UpstreamInvalidResponseError,
    UpstreamUnavailableError,
)


class EmbeddingConnector:
    def __init__(
        self, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.embedding_api_url.strip())

    @property
    def model_name(self) -> str:
        return self.settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.is_configured:
            raise ConnectorNotConfiguredError("Embedding 服务尚未配置。")

        base_url = self.settings.embedding_api_url.rstrip("/")
        url = base_url if base_url.endswith("/embeddings") else f"{base_url}/embeddings"
        token = self.settings.embedding_api_key.get_secret_value()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            with httpx.Client(
                timeout=self.settings.embedding_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json={
                        "model": self.model_name,
                        "input": texts,
                        "encoding_format": "float",
                    },
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, OSError) as exc:
            raise UpstreamUnavailableError("Embedding 服务暂时不可用。") from exc
        except ValueError as exc:
            raise UpstreamInvalidResponseError("Embedding 服务返回了无效 JSON。") from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise UpstreamInvalidResponseError("Embedding 返回数量与输入不一致。")

        indexed: list[tuple[int, list[float]]] = []
        dimension: int | None = None
        for position, item in enumerate(data):
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise UpstreamInvalidResponseError("Embedding 返回缺少向量。")
            try:
                vector = [float(value) for value in item["embedding"]]
                index = int(item.get("index", position))
            except (TypeError, ValueError) as exc:
                raise UpstreamInvalidResponseError("Embedding 向量格式无效。") from exc
            if not vector or any(not math.isfinite(value) for value in vector):
                raise UpstreamInvalidResponseError("Embedding 向量包含无效数值。")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise UpstreamInvalidResponseError("Embedding 向量维度不一致。")
            indexed.append((index, vector))

        indexed.sort(key=lambda item: item[0])
        if [index for index, _ in indexed] != list(range(len(texts))):
            raise UpstreamInvalidResponseError("Embedding 返回索引无效。")
        return [vector for _, vector in indexed]


def get_embedding_connector() -> EmbeddingConnector:
    return EmbeddingConnector(get_settings())
