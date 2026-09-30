from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_category_topic_and_knowledge_point_crud(client: TestClient) -> None:
    category_response = client.post(
        "/api/v1/categories",
        json={"name": "ROS2", "description": "Robot Operating System 2"},
    )
    assert category_response.status_code == 201
    category = category_response.json()
    assert category["slug"] == "ros2"

    topic_response = client.post(
        "/api/v1/topics",
        json={"category_id": category["id"], "name": "QoS"},
    )
    assert topic_response.status_code == 201
    topic = topic_response.json()

    knowledge_response = client.post(
        "/api/v1/knowledge-points",
        json={
            "topic_id": topic["id"],
            "name": "Reliability",
            "description": "Controls delivery reliability.",
        },
    )
    assert knowledge_response.status_code == 201
    knowledge_point = knowledge_response.json()

    assert client.get(f"/api/v1/topics?category_id={category['id']}").json()[0]["name"] == "QoS"
    assert (
        client.get(f"/api/v1/knowledge-points?topic_id={topic['id']}").json()[0]["name"]
        == "Reliability"
    )

    updated = client.patch(
        f"/api/v1/knowledge-points/{knowledge_point['id']}",
        json={"description": "Updated description", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated description"
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/v1/categories/{category['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/topics/{topic['id']}").status_code == 404


def test_duplicate_category_returns_conflict(client: TestClient) -> None:
    payload = {"name": "STM32"}
    assert client.post("/api/v1/categories", json=payload).status_code == 201

    duplicate = client.post("/api/v1/categories", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


def test_child_requires_existing_parent(client: TestClient) -> None:
    response = client.post("/api/v1/topics", json={"category_id": 999, "name": "Missing"})
    assert response.status_code == 404
