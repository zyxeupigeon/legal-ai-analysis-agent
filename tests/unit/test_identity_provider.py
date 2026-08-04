import json

import httpx
import pytest

from services.api.app.identity_provider import (
    OpenAIProviderSettings,
    OpenAIResponsesIdentityProvider,
    ProviderNotConfigured,
    RESEARCH_JSON_SCHEMA,
)


def _response_payload(result: dict, *, include_search_call: bool = True) -> dict:
    output = []
    if include_search_call:
        output.append(
            {
                "type": "web_search_call",
                "id": "ws_1",
                "status": "completed",
                "action": {
                    "sources": [
                        {"type": "url", "url": "https://official.example/product"},
                        {"type": "url", "url": "https://official.example/api"},
                    ]
                },
            }
        )
    output.append(
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": json.dumps(result, ensure_ascii=False),
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://official.example/product",
                            "title": "产品官网",
                            "start_index": 0,
                            "end_index": 4,
                        }
                    ],
                }
            ],
        }
    )
    return {"id": "resp_test", "output": output}


def _clear_result() -> dict:
    return {
        "outcome": "clear",
        "canonical_product_name": "公开法务助手",
        "operator_name": "公开法科公司",
        "product_type": "法律AI助手",
        "is_legal_ai": True,
        "clarification_question": None,
        "candidates": [],
        "related_products": [
            {
                "name": "公开法律API",
                "kind": "api",
                "relationship": "同一运营主体的开发接口",
                "verification_status": "confirmed",
                "source_urls": ["https://official.example/api"],
            }
        ],
        "sources": [
            {
                "url": "https://official.example/api",
                "title": "开发文档",
                "source_type": "official_docs",
                "supports": ["operator", "legal_ai_scope", "api"],
            }
        ],
        "summary": "官方产品页和开发文档共同支持身份结论。",
        "limitations": ["未找到官方MCP文档。"],
    }


def test_openai_provider_sends_web_search_and_strict_schema() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json=_response_payload(_clear_result()))

    provider = OpenAIResponsesIdentityProvider(
        OpenAIProviderSettings(api_key="test-key", model="test-model", base_url="https://api.test/v1"),
        transport=httpx.MockTransport(handler),
    )
    result = provider.research("公开法务助手")

    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["store"] is False
    assert captured["body"]["tools"] == [{"type": "web_search"}]
    assert captured["body"]["include"] == ["web_search_call.action.sources"]
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["body"]["text"]["format"]["schema"] == RESEARCH_JSON_SCHEMA
    assert result.outcome == "clear"
    assert result.web_search_used is True
    assert {item.url for item in result.sources} == {
        "https://official.example/api",
        "https://official.example/product",
    }


def test_ambiguous_result_cannot_expand_ecosystem_and_candidate_ids_are_server_generated() -> None:
    result = _clear_result()
    result.update(
        {
            "outcome": "ambiguous",
            "canonical_product_name": None,
            "operator_name": None,
            "product_type": None,
            "is_legal_ai": None,
            "clarification_question": "你指的是哪一个产品？",
            "candidates": [
                {
                    "id": "model-chosen-id",
                    "product_name": "公开法律助手A",
                    "operator_name": "甲公司",
                    "product_type": "法律AI助手",
                    "is_legal_ai": True,
                    "source_urls": ["https://a.example"],
                }
            ],
        }
    )

    provider = OpenAIResponsesIdentityProvider(
        OpenAIProviderSettings(api_key="test-key", base_url="https://api.test/v1"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=_response_payload(result))),
    )
    researched = provider.research("公开助手")

    assert researched.related_products == []
    assert researched.candidates[0].id.startswith("candidate-")
    assert researched.candidates[0].id != "model-chosen-id"


def test_missing_api_key_fails_without_silent_fixture_fallback() -> None:
    provider = OpenAIResponsesIdentityProvider(OpenAIProviderSettings(api_key=""))
    assert provider.ready is False
    with pytest.raises(ProviderNotConfigured, match="未配置OPENAI_API_KEY"):
        provider.research("任意产品")
