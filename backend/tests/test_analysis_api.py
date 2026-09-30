from fastapi.testclient import TestClient

from app.core.errors import UpstreamInvalidResponseError
from app.integrations.llm import GENERATION_SLOT, get_llm_connector
from app.main import app
from app.schemas.analysis import ErrorAnalysisContent, QuestionVariantsContent
from app.schemas.knowledge_draft import QuizItem
from tests.test_knowledge_drafts_api import FakeLlmConnector
from tests.test_review_api import finish_item, point_with_quiz


class FakeAnalysisConnector(FakeLlmConnector):
    """Extends the draft fake with the two Phase 5 analysis methods."""

    def __init__(self, error_type: str = "concept_confusion", fail: bool = False) -> None:
        super().__init__()
        self.error_type = error_type
        self.fail = fail
        self.variant_questions = ["变式题一？", "变式题二？"]

    def classify_error(self, **kwargs: object) -> ErrorAnalysisContent:
        if self.fail:
            raise UpstreamInvalidResponseError("AI 错题分析内容不符合预期格式。")
        return ErrorAnalysisContent(
            error_type=self.error_type, explanation="反复把两类矩估计搞混。",
            suggestion="重新过一遍一阶矩和二阶矩的定义，再手写一遍公式。",
        )

    def generate_question_variants(self, *, count: int, **kwargs: object) -> QuestionVariantsContent:
        return QuestionVariantsContent(variants=[
            QuizItem(question=self.variant_questions[i % 2], answer=f"答案 {i + 1}")
            for i in range(count)
        ])


def configure(connector: FakeAnalysisConnector) -> None:
    app.dependency_overrides[get_llm_connector] = lambda: connector


def test_overview_flags_weak_point_by_again_streak_and_generates_tip(client: TestClient) -> None:
    point = point_with_quiz(client)
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    for item in session["items"]:
        finish_item(client, item, "again")
    again = client.post(
        "/api/v1/reviews/sessions", json={"knowledge_point_id": point["id"]}
    ).json()
    for item in again["items"]:
        finish_item(client, item, "again")

    overview = client.get("/api/v1/analysis/overview").json()
    assert overview["mastery_distribution"] == {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0}
    assert len(overview["weak_points"]) == 1
    weak = overview["weak_points"][0]
    assert weak["knowledge_point_id"] == point["id"]
    assert weak["again_streak"] == 2
    assert weak["total_again"] == 2
    assert any("没记住" in tip for tip in overview["tips"])


def test_overview_flags_weak_point_stuck_at_low_level(client: TestClient) -> None:
    point = point_with_quiz(client)
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    for item in session["items"]:
        finish_item(client, item, "hard")
    for _ in range(2):
        again = client.post(
            "/api/v1/reviews/sessions", json={"knowledge_point_id": point["id"]}
        ).json()
        for item in again["items"]:
            finish_item(client, item, "hard")

    overview = client.get("/api/v1/analysis/overview").json()
    weak = overview["weak_points"][0]
    assert weak["again_streak"] == 0
    assert weak["level"] == 1
    assert weak["review_count"] == 3
    assert any("变式题" in tip for tip in overview["tips"])


def test_overview_empty_library_has_no_weak_points_or_tips(client: TestClient) -> None:
    overview = client.get("/api/v1/analysis/overview").json()
    assert overview == {
        "mastery_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "weak_points": [], "error_type_distribution": {
            "concept_confusion": 0, "incomplete_recall": 0, "terminology_mixup": 0,
            "slip": 0, "other": 0,
        }, "tips": [],
    }


def test_error_analysis_requires_wrong_answers_then_generates_and_regenerates(client: TestClient) -> None:
    connector = FakeAnalysisConnector()
    configure(connector)
    point = point_with_quiz(client)

    assert client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis/generate"
    ).status_code == 409
    assert client.get(
        f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis"
    ).status_code == 404

    session = client.post("/api/v1/reviews/sessions", json={}).json()
    finish_item(client, session["items"][0], "again")
    finish_item(client, session["items"][1], "good")

    generated = client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis/generate"
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["error_type"] == "concept_confusion"
    assert body["point_name"] == "Adam"
    fetched = client.get(f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis").json()
    assert fetched["id"] == body["id"]

    connector.error_type = "terminology_mixup"
    regenerated = client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis/generate"
    ).json()
    assert regenerated["id"] == body["id"]
    assert regenerated["error_type"] == "terminology_mixup"

    overview = client.get("/api/v1/analysis/overview").json()
    assert overview["error_type_distribution"]["terminology_mixup"] == 1


def test_error_analysis_upstream_invalid_response_surfaces_as_502(client: TestClient) -> None:
    configure(FakeAnalysisConnector(fail=True))
    point = point_with_quiz(client)
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    finish_item(client, session["items"][0], "again")
    finish_item(client, session["items"][1], "good")

    response = client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis/generate"
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_invalid_response"


def test_question_variants_generate_approve_reject_and_regenerate(client: TestClient) -> None:
    connector = FakeAnalysisConnector()
    configure(connector)
    point = point_with_quiz(client)

    generated = client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/question-variants/generate",
        json={"count": 2},
    )
    assert generated.status_code == 200
    variants = generated.json()
    assert len(variants) == 2
    assert all(v["status"] == "pending" for v in variants)

    approved = client.post(
        f"/api/v1/analysis/question-variants/{variants[0]['id']}/approve"
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    rejected = client.post(
        f"/api/v1/analysis/question-variants/{variants[1]['id']}/reject"
    )
    assert rejected.json()["status"] == "rejected"
    # Re-processing is not allowed.
    assert client.post(
        f"/api/v1/analysis/question-variants/{variants[0]['id']}/approve"
    ).status_code == 409

    updated_point = client.get(f"/api/v1/knowledge-points/{point['id']}").json()
    assert len(updated_point["quiz_items"]) == 3
    assert updated_point["quiz_items"][-1]["question"] == variants[0]["question"]

    regenerated = client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/question-variants/generate",
        json={"count": 1},
    ).json()
    assert len(regenerated) == 1
    pending = client.get(
        f"/api/v1/analysis/knowledge-points/{point['id']}/question-variants",
        params={"status": "pending"},
    ).json()
    assert len(pending) == 1
    all_variants = client.get(
        f"/api/v1/analysis/knowledge-points/{point['id']}/question-variants"
    ).json()
    assert len(all_variants) == 3  # 1 approved + 1 rejected + 1 new pending


def test_generation_slot_is_shared_with_knowledge_drafts(client: TestClient) -> None:
    # A single process-wide slot bounds every model call (drafts, error analysis, question
    # variants) to one in flight at a time, per docs/api-design.md. Simulate a draft generation
    # already holding it and confirm analysis generation is blocked by the *same* semaphore
    # rather than one private to app/services/analysis.py.
    connector = FakeAnalysisConnector()
    configure(connector)
    point = point_with_quiz(client)
    session = client.post("/api/v1/reviews/sessions", json={}).json()
    finish_item(client, session["items"][0], "again")
    finish_item(client, session["items"][1], "good")

    assert GENERATION_SLOT.acquire(blocking=False)
    try:
        blocked = client.post(
            f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis/generate"
        )
        assert blocked.status_code == 409
        assert "正在生成" in blocked.json()["error"]["message"]
    finally:
        GENERATION_SLOT.release()

    unblocked = client.post(
        f"/api/v1/analysis/knowledge-points/{point['id']}/error-analysis/generate"
    )
    assert unblocked.status_code == 200


def test_analysis_routes_404_for_unknown_point(client: TestClient) -> None:
    configure(FakeAnalysisConnector())
    assert client.get("/api/v1/analysis/knowledge-points/999/error-analysis").status_code == 404
    assert client.post(
        "/api/v1/analysis/knowledge-points/999/error-analysis/generate"
    ).status_code == 404
    assert client.post(
        "/api/v1/analysis/knowledge-points/999/question-variants/generate", json={"count": 1}
    ).status_code == 404
    assert client.post("/api/v1/analysis/question-variants/999/approve").status_code == 404
