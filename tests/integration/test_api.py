import pytest
from fastapi.testclient import TestClient

from services.api.app.identity_provider import FixtureIdentityResearchProvider
from services.api.app.identity_provider import OpenAIProviderSettings, OpenAIResponsesIdentityProvider
from services.api.app.main import create_app
from services.api.app.store import InMemoryTaskStore


store = InMemoryTaskStore()
client = TestClient(create_app(FixtureIdentityResearchProvider(), store))


@pytest.fixture(autouse=True)
def reset_store() -> None:
    store.clear()


def create(product_name: str):
    return client.post("/api/tasks", json={"product_name": product_name})


def test_health_declares_explicit_fixture_mode() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_version": "0.2.0",
        "storage_mode": "memory_only",
        "classifier_mode": "deterministic_fixture",
        "provider_ready": True,
        "model_name": None,
        "message": "显式测试模式：使用虚构确定性数据，不代表真实公开检索。",
    }


def test_clear_product_reaches_p2_phase_limit() -> None:
    response = create("衡法智研")
    assert response.status_code == 201
    task = response.json()
    assert task["task_status"] == "研究中"
    assert task["identity_gate"] == "confirmed"
    assert task["phase_limit_reached"] is True
    assert len(task["related_product_hints"]) == 2
    assert len(task["events"]) == 1


def test_ambiguous_product_stops_and_does_not_expand_scope() -> None:
    response = create("星云助手")
    task = response.json()
    assert task["task_status"] == "等待产品确认"
    assert task["identity_gate"] == "awaiting_user"
    assert task["canonical_product_name"] is None
    assert task["related_product_hints"] == []
    assert len(task["candidates"]) == 2


def test_candidate_confirmation_resumes_at_research_boundary() -> None:
    task = create("星云助手").json()
    legal_candidate = next(item for item in task["candidates"] if item["is_legal_ai"])
    response = client.post(
        f"/api/tasks/{task['task_id']}/clarifications",
        json={"candidate_id": legal_candidate["id"]},
    )
    assert response.status_code == 200
    clarified = response.json()
    assert clarified["task_status"] == "研究中"
    assert clarified["identity_gate"] == "confirmed"
    assert clarified["canonical_product_name"] == "星云法律助手"
    assert len(clarified["events"]) == 2


def test_non_legal_candidate_terminates() -> None:
    task = create("星云助手").json()
    non_legal = next(item for item in task["candidates"] if not item["is_legal_ai"])
    response = client.post(
        f"/api/tasks/{task['task_id']}/clarifications",
        json={"candidate_id": non_legal["id"]},
    )
    assert response.status_code == 200
    assert response.json()["task_status"] == "已终止"
    assert response.json()["identity_gate"] == "rejected"


def test_user_exact_name_is_researched_again_and_can_remain_ambiguous() -> None:
    task = create("未收录产品名称").json()
    response = client.post(
        f"/api/tasks/{task['task_id']}/clarifications",
        json={"confirmed_product_name": "用户确认的产品全称"},
    )
    clarified = response.json()
    assert clarified["identity_gate"] == "awaiting_user"
    assert clarified["operator_name"] is None
    assert clarified["product_type"] is None
    assert len(clarified["events"]) == 1


def test_out_of_scope_product_terminates_without_report_work() -> None:
    task = create("晴空天气").json()
    assert task["task_status"] == "已终止"
    assert task["identity_gate"] == "rejected"
    assert task["next_action"] is None
    assert task["related_product_hints"] == []


def test_empty_name_is_rejected() -> None:
    response = create("   ")
    assert response.status_code == 422


def test_invalid_clarification_is_rejected() -> None:
    task = create("法律AI").json()
    response = client.post(
        f"/api/tasks/{task['task_id']}/clarifications",
        json={"candidate_id": "missing"},
    )
    assert response.status_code == 409


def test_task_list_and_read() -> None:
    task = create("衡法智研").json()
    assert client.get(f"/api/tasks/{task['task_id']}").status_code == 200
    listed = client.get("/api/tasks").json()
    assert [item["task_id"] for item in listed] == [task["task_id"]]


def test_missing_task_returns_404() -> None:
    assert client.get("/api/tasks/not-found").status_code == 404


def test_missing_key_is_visible_and_does_not_create_a_task() -> None:
    isolated_store = InMemoryTaskStore()
    provider = OpenAIResponsesIdentityProvider(OpenAIProviderSettings(api_key=""))
    isolated_client = TestClient(create_app(provider, isolated_store))

    health = isolated_client.get("/api/health").json()
    assert health["status"] == "needs_configuration"
    assert health["provider_ready"] is False

    response = isolated_client.post("/api/tasks", json={"product_name": "任意产品"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
    assert isolated_store.list() == []
