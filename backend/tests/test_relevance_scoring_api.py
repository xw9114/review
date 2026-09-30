from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.errors import UpstreamUnavailableError
from app.integrations.embedding import EmbeddingConnector, get_embedding_connector
from app.integrations.notebook import get_notebook_connector
from app.schemas.source_document import NotebookEntry
from app.main import app


class FakeNotebookConnector:
    def __init__(self, entries: list[NotebookEntry]) -> None:
        self.entries = entries

    def fetch_entries(self) -> list[NotebookEntry]:
        return self.entries


class FakeEmbeddingConnector:
    def __init__(self, *, configured: bool = True, fail: bool = False) -> None:
        self.is_configured = configured
        self.model_name = "test-embedding"
        self.fail = fail
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail:
            raise UpstreamUnavailableError("test embedding unavailable")
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.casefold()
            if "optimizer" in lowered or "优化器" in lowered or "adam" in lowered:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors


def configure_scoring(
    client: TestClient,
    connector: FakeEmbeddingConnector,
    entries: list[NotebookEntry],
) -> None:
    settings = Settings(
        embedding_api_url="https://embedding.example/v1" if connector.is_configured else "",
        embedding_model=connector.model_name,
        relevance_threshold=0.6,
        relevance_batch_size=20,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_embedding_connector] = lambda: connector
    app.dependency_overrides[get_notebook_connector] = lambda: FakeNotebookConnector(entries)


def create_structure_and_sources(client: TestClient, count: int = 1) -> int:
    category = client.post(
        "/api/v1/categories",
        json={"name": "深度学习", "description": "模型训练"},
    ).json()
    topic = client.post(
        "/api/v1/topics",
        json={
            "category_id": category["id"],
            "name": "Optimizer",
            "description": "优化器",
        },
    ).json()
    response = client.post("/api/v1/source-connectors/notebook/sync")
    assert response.status_code == 200
    assert response.json()["created"] == count
    return topic["id"]


def test_embedding_batch_scores_and_reuses_topic_vector(client: TestClient) -> None:
    connector = FakeEmbeddingConnector()
    entries = [
        NotebookEntry(
            external_id=str(index),
            title=f"Adam 优化器实践 {index}",
            content="Adam 是常用的深度学习优化器。",
            created_at=datetime(2026, 9, 24, index, tzinfo=UTC),
        )
        for index in (1, 2)
    ]
    configure_scoring(client, connector, entries)
    topic_id = create_structure_and_sources(client, count=2)

    response = client.post("/api/v1/source-documents/score-pending")
    assert response.status_code == 200
    assert response.json() == {
        "requested": 2,
        "scored": 2,
        "failed": 0,
        "embedding": 2,
        "keyword": 0,
        "passed": 2,
        "threshold": 0.6,
    }
    # One batch call covering the uncached topic plus both uncached documents, instead of one
    # call per document.
    assert [len(call) for call in connector.calls] == [3]

    documents = client.get("/api/v1/source-documents?status=pending").json()
    assert all(document["processing_status"] == "scored" for document in documents)
    assert all(document["relevance_method"] == "embedding" for document in documents)
    assert all(document["relevance_score"] == 1.0 for document in documents)
    assert all(document["relevance_passed"] is True for document in documents)
    assert all(document["suggested_topic_id"] == topic_id for document in documents)

    second_response = client.post("/api/v1/source-documents/score-pending")
    assert second_response.status_code == 200
    assert second_response.json()["requested"] == 0
    assert [len(call) for call in connector.calls] == [3]


def test_embedding_batch_call_count_does_not_grow_with_document_count(client: TestClient) -> None:
    connector = FakeEmbeddingConnector()
    entries = [
        NotebookEntry(
            external_id=str(index),
            title=f"Adam 优化器实践 {index}",
            content="Adam 是常用的深度学习优化器。",
            created_at=datetime(2026, 9, 24, index, tzinfo=UTC),
        )
        for index in range(5)
    ]
    configure_scoring(client, connector, entries)
    create_structure_and_sources(client, count=5)

    response = client.post("/api/v1/source-documents/score-pending")
    assert response.status_code == 200
    assert response.json()["scored"] == 5
    # Still exactly one HTTP call (1 topic + 5 documents = 6 texts), not one call per document.
    assert connector.calls == [connector.calls[0]]
    assert len(connector.calls[0]) == 6


def test_unconfigured_embedding_uses_keyword_fallback(client: TestClient) -> None:
    connector = FakeEmbeddingConnector(configured=False)
    entries = [
        NotebookEntry(
            external_id="keyword",
            title="Optimizer 与优化器选择",
            content="深度学习训练时如何选择优化器。",
            created_at=datetime(2026, 9, 24, tzinfo=UTC),
        )
    ]
    configure_scoring(client, connector, entries)
    topic_id = create_structure_and_sources(client)

    response = client.post("/api/v1/source-documents/score-pending")
    assert response.status_code == 200
    result = response.json()
    assert result["keyword"] == 1
    assert result["embedding"] == 0
    assert result["passed"] == 1
    assert connector.calls == []

    document = client.get("/api/v1/source-documents?status=pending").json()[0]
    assert document["relevance_method"] == "keyword"
    assert document["suggested_topic_id"] == topic_id
    assert "Optimizer" in document["relevance_reason"]


def test_batch_records_embedding_failure_without_losing_source(client: TestClient) -> None:
    connector = FakeEmbeddingConnector(fail=True)
    entries = [
        NotebookEntry(
            external_id="failure",
            title="Adam",
            content="优化器资料",
            created_at=datetime(2026, 9, 24, tzinfo=UTC),
        )
    ]
    configure_scoring(client, connector, entries)
    create_structure_and_sources(client)

    response = client.post("/api/v1/source-documents/score-pending")
    assert response.status_code == 200
    assert response.json()["failed"] == 1
    document = client.get("/api/v1/source-documents?status=pending").json()[0]
    assert document["processing_status"] == "failed"
    assert document["status"] == "pending"


def test_embedding_connector_validates_and_orders_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://embedding.example/v1/embeddings"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 1]},
                    {"index": 0, "embedding": [1, 0]},
                ]
            },
        )

    connector = EmbeddingConnector(
        Settings(
            embedding_api_url="https://embedding.example/v1",
            embedding_api_key="secret",
            embedding_model="test-embedding",
        ),
        transport=httpx.MockTransport(handler),
    )
    assert connector.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_topic_change_invalidates_existing_relevance_scores(client: TestClient) -> None:
    connector = FakeEmbeddingConnector(configured=False)
    entries = [
        NotebookEntry(
            external_id="taxonomy-change",
            title="Optimizer 与优化器选择",
            content="深度学习训练资料。",
            created_at=datetime(2026, 9, 24, tzinfo=UTC),
        )
    ]
    configure_scoring(client, connector, entries)
    topic_id = create_structure_and_sources(client)
    assert client.post("/api/v1/source-documents/score-pending").json()["scored"] == 1

    response = client.patch(
        f"/api/v1/topics/{topic_id}",
        json={"description": "新的主题语义说明"},
    )
    assert response.status_code == 200
    document = client.get("/api/v1/source-documents?status=pending").json()[0]
    assert document["processing_status"] == "unscored"
    assert document["relevance_score"] is None
    assert document["suggested_topic_id"] is None
