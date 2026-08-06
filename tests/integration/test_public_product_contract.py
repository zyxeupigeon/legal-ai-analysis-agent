import json

import httpx
from fastapi.testclient import TestClient

from services.api.app.identity_provider import OpenAIProviderSettings, OpenAIResponsesIdentityProvider
from services.api.app.main import create_app
from services.api.app.store import InMemoryTaskStore


def test_recorded_public_product_result_flows_through_real_provider_contract() -> None:
    """Public facts recorded 2026-08-04; network is mocked so CI remains deterministic."""
    result = {
        "outcome": "clear",
        "canonical_product_name": "得理法搜",
        "operator_name": "深圳得理科技有限公司",
        "product_type": "法律AI检索与研究产品",
        "is_legal_ai": True,
        "clarification_question": None,
        "candidates": [],
        "related_products": [
            {
                "name": "得理开放API",
                "kind": "api",
                "relationship": "官网列出的同企业法律大模型和法律检索API入口",
                "verification_status": "confirmed",
                "source_urls": ["https://www.delilegal.com/"],
            }
        ],
        "sources": [
            {
                "url": "https://apps.apple.com/cn/app/id1512357117",
                "title": "得理法搜 App Store页面",
                "source_type": "official_product",
                "supports": ["identity", "operator", "legal_ai_scope"],
            },
            {
                "url": "https://www.delilegal.com/",
                "title": "得理官网",
                "source_type": "official_company",
                "supports": ["operator", "ecosystem", "api"],
            },
        ],
        "summary": "公开产品页和企业官网支持产品身份、运营主体及法律AI用途。",
        "limitations": ["未在已核验官方页面确认得理MCP服务。"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        assert request_body["tools"] == [{"type": "web_search"}]
        assert request_body["store"] is False
        return httpx.Response(
            200,
            json={
                "output": [
                    {"type": "web_search_call", "status": "completed"},
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(result), "annotations": []}],
                    },
                ]
            },
        )

    provider = OpenAIResponsesIdentityProvider(
        OpenAIProviderSettings(api_key="test-key", base_url="https://api.test/v1"),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(create_app(provider, InMemoryTaskStore()))
    response = client.post("/api/tasks", json={"product_name": "得理法搜"})

    assert response.status_code == 201
    task = response.json()
    assert task["identity_gate"] == "confirmed"
    assert task["operator_name"] == "深圳得理科技有限公司"
    assert task["related_products"][0]["kind"] == "api"
    assert all(item["kind"] != "mcp" for item in task["related_products"])
    assert task["web_search_used"] is True
    assert task["phase_limit_reached"] is False
