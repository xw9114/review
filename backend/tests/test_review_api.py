from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services.reviews import next_schedule


def point_with_quiz(client: TestClient):
    category = client.post("/api/v1/categories", json={"name": "复习测试"}).json()
    topic = client.post("/api/v1/topics", json={"category_id": category["id"], "name": "优化器"}).json()
    response = client.post("/api/v1/knowledge-points", json={
        "topic_id": topic["id"], "name": "Adam",
        "quiz_items": [{"question": "一阶矩是什么？", "answer": "梯度的移动平均"},
                       {"question": "二阶矩是什么？", "answer": "梯度平方的移动平均"}],
    })
    assert response.status_code == 201
    return response.json()


def finish_item(client, item, rating="good", user_answer="我的答案"):
    shown = client.post(f"/api/v1/reviews/items/{item['id']}/reveal", json={"user_answer": user_answer})
    assert shown.status_code == 200
    assert next(i for i in shown.json()["items"] if i["id"] == item["id"])["standard_answer"]
    result = client.post(f"/api/v1/reviews/items/{item['id']}/answer", json={"rating": rating, "user_answer": user_answer})
    assert result.status_code == 200
    return result.json()


def test_complete_review_resume_and_idempotent_answers(client: TestClient):
    point_with_quiz(client)
    assert client.get("/api/v1/reviews/overview").json()["due_count"] == 1
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    assert len(session["items"]) == 2
    assert all(item["standard_answer"] is None for item in session["items"])
    assert client.post("/api/v1/reviews/sessions", json={}).json()["id"] == session["id"]
    assert client.get("/api/v1/reviews/active").json()["id"] == session["id"]
    item = session["items"][0]
    assert client.post(f"/api/v1/reviews/items/{item['id']}/answer", json={"rating": "good"}).status_code == 409
    finish_item(client, item, "hard")
    assert client.get("/api/v1/reviews/overview").json()["points"][0]["review_count"] == 0
    completed = finish_item(client, session["items"][1], "easy")
    assert completed["status"] == "completed"
    assert client.get("/api/v1/reviews/active").json() is None
    stats = client.get("/api/v1/reviews/overview").json()
    assert stats["due_count"] == 0
    assert stats["reviewed_today"] == 2
    assert stats["points"][0]["review_count"] == 1
    assert stats["points"][0]["level"] == 1  # weakest response is 'hard'
    assert stats["completed_sessions"] == 1
    assert stats["recent_sessions"][0]["id"] == session["id"]
    assert stats["recent_sessions"][0]["question_count"] == 2
    retry = client.post(f"/api/v1/reviews/items/{item['id']}/answer", json={"rating": "hard", "user_answer": "我的答案"})
    assert retry.status_code == 200
    assert client.get("/api/v1/reviews/overview").json()["points"][0]["review_count"] == 1
    assert client.post(f"/api/v1/reviews/items/{item['id']}/answer", json={"rating": "easy"}).status_code == 409


def test_question_changes_preserve_snapshot_and_reset_due_state(client: TestClient):
    point = point_with_quiz(client)
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    client.patch(f"/api/v1/knowledge-points/{point['id']}", json={"quiz_items": [{"question": "新题？", "answer": "新答案"}]})
    for item in session["items"]:
        finish_item(client, item)
    saved = client.get(f"/api/v1/reviews/sessions/{session['id']}").json()
    assert saved["items"][0]["question"] == "一阶矩是什么？"
    stats = client.get("/api/v1/reviews/overview").json()
    assert stats["due_count"] == 1
    assert stats["points"][0]["review_count"] == 0
    assert client.post("/api/v1/reviews/sessions", json={}).json()["items"][0]["question"] == "新题？"


def test_deleted_point_keeps_answer_history(client: TestClient):
    point = point_with_quiz(client)
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    assert client.delete(f"/api/v1/knowledge-points/{point['id']}").status_code == 204
    for item in session["items"]:
        finish_item(client, item)
    saved = client.get(f"/api/v1/reviews/sessions/{session['id']}").json()
    assert saved["status"] == "completed"
    assert saved["items"][0]["point_name"] == "Adam"
    assert saved["items"][0]["knowledge_point_id"] is None


def test_invalid_review_data_and_empty_library(client: TestClient):
    assert client.post("/api/v1/reviews/sessions", json={}).status_code == 409
    assert client.post("/api/v1/reviews/sessions", json={"limit": 100}).status_code == 422
    assert client.get("/api/v1/reviews/sessions/999").status_code == 404
    assert client.post("/api/v1/reviews/items/999/reveal", json={}).status_code == 404
    point = point_with_quiz(client)
    assert client.patch(f"/api/v1/knowledge-points/{point['id']}", json={"quiz_items": [{"question": "  ", "answer": "A"}]}).status_code == 422


@pytest.mark.parametrize("level,rating,expected_level,delta", [
    (5, "again", 1, timedelta(minutes=10)), (4, "hard", 3, timedelta(days=1)),
    (1, "good", 2, timedelta(days=3)), (1, "easy", 3, timedelta(days=7)),
    (5, "easy", 5, timedelta(days=30)), (5, "good", 5, timedelta(days=30)),
])
def test_deterministic_schedule(level, rating, expected_level, delta):
    now = datetime(2026, 9, 26, tzinfo=UTC)
    assert next_schedule(level, rating, now) == (expected_level, now + delta)
