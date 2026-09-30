from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import UpstreamInvalidResponseError
from app.integrations.llm import LlmConnector, get_llm_connector
from app.integrations.notebook import get_notebook_connector
from app.schemas.knowledge_draft import DraftContent, QuizItem
from app.schemas.source_document import NotebookEntry
from app.main import app


class MutableNotebookConnector:
    def __init__(self, entries: list[NotebookEntry]) -> None:
        self.entries = entries

    def fetch_entries(self) -> list[NotebookEntry]:
        return self.entries


class FakeLlmConnector:
    model_name = "test-draft-model"

    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def generate_draft(self, **kwargs: str | None) -> DraftContent:
        self.calls.append(kwargs)
        return DraftContent(
            title="Adam 优化器的核心机制",
            summary="Adam 结合一阶与二阶矩估计，自适应调整每个参数的学习率。",
            difficulty="intermediate",
            key_points=["动量估计", "自适应学习率"],
            quiz_items=[
                QuizItem(
                    question="Adam 维护哪两类矩估计？",
                    answer="梯度的一阶矩与二阶矩估计。",
                )
            ],
        )


def configure(
    connector: FakeLlmConnector | LlmConnector,
    entries: list[NotebookEntry],
) -> MutableNotebookConnector:
    notebook = MutableNotebookConnector(entries)
    app.dependency_overrides[get_llm_connector] = lambda: connector
    app.dependency_overrides[get_notebook_connector] = lambda: notebook
    return notebook


def create_topic_and_source(client: TestClient) -> tuple[int, int]:
    category = client.post(
        "/api/v1/categories", json={"name": "深度学习", "description": "模型训练"}
    ).json()
    topic = client.post(
        "/api/v1/topics",
        json={
            "category_id": category["id"],
            "name": "Optimizer",
            "description": "优化器与梯度下降",
        },
    ).json()
    assert client.post("/api/v1/source-connectors/notebook/sync").status_code == 200
    source = client.get("/api/v1/source-documents?status=pending").json()[0]
    return topic["id"], source["id"]


def entry(content: str = "Adam 结合动量和自适应学习率。") -> NotebookEntry:
    return NotebookEntry(
        external_id="draft-source",
        title="Adam 优化器",
        content=content,
        created_at=datetime(2026, 9, 24, tzinfo=UTC),
    )


def test_generate_edit_approve_draft_is_atomic(client: TestClient) -> None:
    connector = FakeLlmConnector()
    configure(connector, [entry()])
    topic_id, source_id = create_topic_and_source(client)

    response = client.post(
        f"/api/v1/source-documents/{source_id}/draft/generate",
        json={"topic_id": topic_id},
    )
    assert response.status_code == 200
    draft = response.json()
    assert draft["status"] == "draft"
    assert draft["generation_count"] == 1
    assert draft["model"] == connector.model_name
    assert draft["source_title"] == "Adam 优化器"
    assert client.get(f"/api/v1/source-documents/{source_id}").json()["status"] == "pending"

    regenerated = client.post(
        f"/api/v1/source-documents/{source_id}/draft/generate",
        json={"topic_id": topic_id, "regenerate": True},
    ).json()
    assert regenerated["id"] == draft["id"]
    assert regenerated["generation_count"] == 2

    review = {
        "topic_id": topic_id,
        "title": "Adam 优化器笔记",
        "summary": "人工修改后的摘要。",
        "difficulty": "advanced",
        "key_points": ["偏差修正", "一阶矩", "二阶矩"],
        "quiz_items": [{"question": "为什么要偏差修正？", "answer": "减少初始阶段的估计偏差。"}],
    }
    saved = client.patch(f"/api/v1/knowledge-drafts/{draft['id']}", json=review)
    assert saved.status_code == 200
    assert saved.json()["title"] == review["title"]

    approved = client.post(
        f"/api/v1/knowledge-drafts/{draft['id']}/approve", json=review
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["knowledge_point_id"] is not None

    source = client.get(f"/api/v1/source-documents/{source_id}").json()
    assert source["status"] == "accepted"
    point = client.get("/api/v1/knowledge-points").json()[0]
    assert point["summary"] == review["summary"]
    assert point["difficulty"] == "advanced"
    assert point["key_points"] == review["key_points"]
    assert point["quiz_items"] == review["quiz_items"]
    assert point["source_document_ids"] == [source_id]
    assert client.post(
        f"/api/v1/knowledge-drafts/{draft['id']}/approve", json=review
    ).status_code == 409
    # Removing derived knowledge must not delete its source or approved draft history.
    assert client.delete(f"/api/v1/knowledge-points/{point['id']}").status_code == 204
    assert client.get(f"/api/v1/source-documents/{source_id}").json()["id"] == source_id
    assert client.get(f"/api/v1/knowledge-drafts/{draft['id']}").json()["knowledge_point_id"] is None


def test_reject_keeps_source_pending(client: TestClient) -> None:
    configure(FakeLlmConnector(), [entry()])
    topic_id, source_id = create_topic_and_source(client)
    draft = client.post(
        f"/api/v1/source-documents/{source_id}/draft/generate",
        json={"topic_id": topic_id},
    ).json()

    rejected = client.post(f"/api/v1/knowledge-drafts/{draft['id']}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get(f"/api/v1/source-documents/{source_id}").json()["status"] == "pending"


def test_direct_source_decision_retires_open_draft(client: TestClient) -> None:
    configure(FakeLlmConnector(), [entry()])
    topic_id, source_id = create_topic_and_source(client)
    draft = client.post(
        f"/api/v1/source-documents/{source_id}/draft/generate",
        json={"topic_id": topic_id},
    ).json()

    assert client.post(f"/api/v1/source-documents/{source_id}/ignore").status_code == 200
    retired = client.get(f"/api/v1/knowledge-drafts/{draft['id']}").json()
    assert retired["status"] == "rejected"


def test_source_change_marks_draft_stale(client: TestClient) -> None:
    notebook = configure(FakeLlmConnector(), [entry()])
    topic_id, source_id = create_topic_and_source(client)
    draft = client.post(
        f"/api/v1/source-documents/{source_id}/draft/generate",
        json={"topic_id": topic_id},
    ).json()

    notebook.entries = [entry("原文已经修改，需要重新生成。")]
    assert client.post("/api/v1/source-connectors/notebook/sync").json()["updated"] == 1
    stale = client.get(f"/api/v1/knowledge-drafts/{draft['id']}").json()
    assert stale["status"] == "stale"


def test_unconfigured_llm_does_not_create_draft(client: TestClient) -> None:
    connector = LlmConnector(Settings(llm_api_url="", llm_model=""))
    configure(connector, [entry()])
    topic_id, source_id = create_topic_and_source(client)

    response = client.post(
        f"/api/v1/source-documents/{source_id}/draft/generate",
        json={"topic_id": topic_id},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "connector_not_configured"
    assert client.get("/api/v1/knowledge-drafts").json() == []


def test_llm_connector_rejects_invalid_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "OpenAI/Python 2.6.1"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"title":"missing fields"}'}}]},
        )

    connector = LlmConnector(
        Settings(
            llm_api_url="https://llm.example/v1",
            llm_api_key="secret",
            llm_model="draft-model",
        ),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(UpstreamInvalidResponseError):
        connector.generate_draft(
            source_title="title",
            source_content="content",
            category_name="category",
            topic_name="topic",
            topic_description=None,
        )


def review_payload(draft: dict) -> dict:
    return {key: draft[key] for key in (
        "topic_id", "title", "summary", "difficulty", "key_points", "quiz_items"
    )} | {"expected_revision": draft["revision"]}


def test_reopen_reuses_saved_draft_and_versions_prevent_lost_edits(client: TestClient) -> None:
    connector = FakeLlmConnector()
    configure(connector, [entry()])
    topic_id, source_id = create_topic_and_source(client)
    url = f"/api/v1/source-documents/{source_id}/draft/generate"
    draft = client.post(url, json={"topic_id": topic_id}).json()
    payload = review_payload(draft) | {"title": "我的人工修改"}
    saved = client.patch(f"/api/v1/knowledge-drafts/{draft['id']}", json=payload).json()
    assert saved["revision"] > draft["revision"]
    reopened = client.post(url, json={"topic_id": topic_id}).json()
    assert reopened["title"] == "我的人工修改"
    assert reopened["generation_count"] == 1
    assert len(connector.calls) == 1
    assert client.patch(f"/api/v1/knowledge-drafts/{draft['id']}", json=payload).status_code == 409
    assert client.post(f"/api/v1/knowledge-drafts/{draft['id']}/approve", json=payload).status_code == 409
    assert client.post(f"/api/v1/knowledge-drafts/{draft['id']}/reject?expected_revision={draft['revision']}").status_code == 409
    assert client.post(url, json={"topic_id": topic_id, "regenerate": True, "expected_revision": draft["revision"]}).status_code == 409
    assert len(connector.calls) == 1
    assert client.get("/api/v1/knowledge-points").json() == []


def test_source_update_during_generation_discards_result(client: TestClient) -> None:
    connector = FakeLlmConnector()
    notebook = configure(connector, [entry()])
    topic_id, source_id = create_topic_and_source(client)
    original_generate = connector.generate_draft

    def delayed_generate(**kwargs):
        notebook.entries = [entry("同步期间原资料已经更新。")]
        assert client.post("/api/v1/source-connectors/notebook/sync").status_code == 200
        return original_generate(**kwargs)

    connector.generate_draft = delayed_generate
    result = client.post(f"/api/v1/source-documents/{source_id}/draft/generate", json={"topic_id": topic_id})
    assert result.status_code == 409
    assert client.get("/api/v1/knowledge-drafts").json() == []


def test_human_edit_during_regeneration_is_not_overwritten(client: TestClient) -> None:
    connector = FakeLlmConnector()
    configure(connector, [entry()])
    topic_id, source_id = create_topic_and_source(client)
    url = f"/api/v1/source-documents/{source_id}/draft/generate"
    draft = client.post(url, json={"topic_id": topic_id}).json()
    original_generate = connector.generate_draft

    def delayed_generate(**kwargs):
        update = review_payload(draft) | {"title": "等待生成时保存的人工内容"}
        assert client.patch(f"/api/v1/knowledge-drafts/{draft['id']}", json=update).status_code == 200
        return original_generate(**kwargs)

    connector.generate_draft = delayed_generate
    result = client.post(url, json={"topic_id": topic_id, "regenerate": True, "expected_revision": draft["revision"]})
    assert result.status_code == 409
    assert client.get(f"/api/v1/knowledge-drafts/{draft['id']}").json()["title"] == "等待生成时保存的人工内容"


def test_blank_fields_and_retired_drafts_cannot_be_approved(client: TestClient) -> None:
    configure(FakeLlmConnector(), [entry()])
    topic_id, source_id = create_topic_and_source(client)
    draft = client.post(f"/api/v1/source-documents/{source_id}/draft/generate", json={"topic_id": topic_id}).json()
    payload = review_payload(draft)
    for key in ("title", "summary"):
        assert client.patch(f"/api/v1/knowledge-drafts/{draft['id']}", json=payload | {key: "   "}).status_code == 422
    assert client.post(f"/api/v1/source-documents/{source_id}/ignore").status_code == 200
    payload.pop("expected_revision")
    assert client.patch(f"/api/v1/knowledge-drafts/{draft['id']}", json=payload).status_code == 409
    assert client.post(f"/api/v1/knowledge-drafts/{draft['id']}/approve", json=payload).status_code == 409
