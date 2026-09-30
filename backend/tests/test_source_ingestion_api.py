from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import UpstreamInvalidResponseError, UpstreamUnavailableError
from app.integrations.notebook import NotebookConnector, get_notebook_connector
from app.schemas.source_document import NotebookEntry


class FakeNotebookConnector:
    def __init__(self, entries: list[NotebookEntry]) -> None:
        self.entries = entries

    def fetch_entries(self) -> list[NotebookEntry]:
        return self.entries


def note(external_id: str, title: str, content: str) -> NotebookEntry:
    return NotebookEntry(
        external_id=external_id,
        title=title,
        content=content,
        created_at=datetime(2026, 9, 20, 8, 0, tzinfo=UTC),
    )


def create_topic(client: TestClient) -> int:
    category = client.post("/api/v1/categories", json={"name": "个人成长"}).json()
    topic = client.post(
        "/api/v1/topics", json={"category_id": category["id"], "name": "学习方法"}
    ).json()
    return topic["id"]


def use_entries(client: TestClient, entries: list[NotebookEntry]) -> FakeNotebookConnector:
    connector = FakeNotebookConnector(entries)
    client.app.dependency_overrides[get_notebook_connector] = lambda: connector
    return connector


def test_sync_is_idempotent_and_accepts_source(client: TestClient) -> None:
    topic_id = create_topic(client)
    connector = use_entries(
        client,
        [
            note("12", "复盘阅读方法", "先提出问题，再带着问题阅读。"),
            note("13", "费曼技巧", "尝试用自己的话解释。"),
        ],
    )

    first = client.post("/api/v1/source-connectors/notebook/sync")
    assert first.status_code == 200
    assert first.json() == {
        "created": 2,
        "updated": 0,
        "unchanged": 0,
        "stale": 0,
        "total": 2,
    }

    second = client.post("/api/v1/source-connectors/notebook/sync")
    assert second.status_code == 200
    assert second.json()["unchanged"] == 2
    pending = client.get("/api/v1/source-documents?status=pending").json()
    assert len(pending) == 2

    source = next(item for item in pending if item["external_id"] == "12")
    accepted = client.post(
        f"/api/v1/source-documents/{source['id']}/accept",
        json={
            "topic_id": topic_id,
            "name": "主动阅读",
            "description": source["content"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    knowledge_point_id = accepted.json()["knowledge_point_id"]
    knowledge_point = client.get(f"/api/v1/knowledge-points/{knowledge_point_id}").json()
    assert knowledge_point["name"] == "主动阅读"

    duplicate = client.post(
        f"/api/v1/source-documents/{source['id']}/accept",
        json={"topic_id": topic_id, "name": "主动阅读"},
    )
    assert duplicate.status_code == 409

    connector.entries[0] = note("12", "复盘阅读方法", "先列问题，再阅读并复述答案。")
    changed = client.post("/api/v1/source-connectors/notebook/sync")
    assert changed.json()["updated"] == 1
    refreshed = client.get(f"/api/v1/source-documents/{source['id']}").json()
    assert refreshed["status"] == "pending"
    assert refreshed["knowledge_point_id"] == knowledge_point_id

    updated = client.post(
        f"/api/v1/source-documents/{source['id']}/accept",
        json={
            "topic_id": topic_id,
            "name": "主动阅读（更新）",
            "description": refreshed["content"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["knowledge_point_id"] == knowledge_point_id
    assert client.get(f"/api/v1/knowledge-points/{knowledge_point_id}").json()["name"] == "主动阅读（更新）"


def test_missing_sources_become_stale_without_deleting_knowledge(client: TestClient) -> None:
    topic_id = create_topic(client)
    connector = use_entries(client, [note("21", "保留来源", "这条笔记稍后会从日序消失。")])
    assert client.post("/api/v1/source-connectors/notebook/sync").status_code == 200
    source = client.get("/api/v1/source-documents?status=pending").json()[0]
    accepted = client.post(
        f"/api/v1/source-documents/{source['id']}/accept",
        json={"topic_id": topic_id, "name": "来源保留", "description": source["content"]},
    ).json()

    connector.entries = []
    sync = client.post("/api/v1/source-connectors/notebook/sync")
    assert sync.json()["stale"] == 1
    stale = client.get("/api/v1/source-documents?status=stale").json()
    assert stale[0]["knowledge_point_id"] == accepted["knowledge_point_id"]
    assert (
        client.get(f"/api/v1/knowledge-points/{accepted['knowledge_point_id']}").status_code
        == 200
    )


def test_ignore_and_validation_states(client: TestClient) -> None:
    use_entries(client, [note("31", "暂不整理", "这条先留在资料库。")])
    client.post("/api/v1/source-connectors/notebook/sync")
    source = client.get("/api/v1/source-documents?status=pending").json()[0]

    ignored = client.post(f"/api/v1/source-documents/{source['id']}/ignore")
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"
    assert client.get("/api/v1/source-documents?status=unknown").status_code == 422

    missing_topic = client.post(
        f"/api/v1/source-documents/{source['id']}/accept",
        json={"topic_id": 999, "name": "不会创建"},
    )
    assert missing_topic.status_code == 404


def test_unconfigured_notebook_returns_stable_error(client: TestClient) -> None:
    response = client.post("/api/v1/source-connectors/notebook/sync")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "connector_not_configured"


def test_notebook_connector_rejects_incomplete_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://notes.example.test/internal/v1/entries")
    response = httpx.Response(
        200,
        request=request,
        json={
            "total": 2,
            "items": [
                {
                    "external_id": "1",
                    "title": "Only one item",
                    "content": "",
                    "created_at": "2026-09-20T08:00:00+08:00",
                }
            ],
        },
    )
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)
    connector = NotebookConnector(
        Settings(notebook_api_url="https://notes.example.test", notebook_api_token="token")
    )

    with pytest.raises(UpstreamInvalidResponseError):
        connector.fetch_entries()


def test_notebook_connector_maps_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", fail)
    connector = NotebookConnector(
        Settings(notebook_api_url="https://notes.example.test", notebook_api_token="token")
    )

    with pytest.raises(UpstreamUnavailableError):
        connector.fetch_entries()
