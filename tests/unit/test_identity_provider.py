import json

import httpx
import pytest

from services.api.app.identity_provider import (
    ExternalSearchIdentityProvider,
    OpenAIProviderSettings,
    OpenAIResponsesIdentityProvider,
    ProviderNotConfigured,
    RESEARCH_JSON_SCHEMA,
)
from services.api.app.provider_errors import ProviderUnavailable
from services.api.app.search_provider import SearchDocument


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


class _SequenceModel:
    provider_name = "deepseek"
    model_name = "test-model"
    ready = True
    readiness_message = "ready"

    def __init__(self, results: list[dict]) -> None:
        self.results = list(results)
        self.prompts: list[str] = []

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append(user_prompt)
        return json.dumps(self.results.pop(0), ensure_ascii=False)


class _RecordedSearch:
    provider_name = "recorded_search"
    search_tier = "test"
    ready = True
    readiness_message = "ready"

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, *, max_results: int = 5) -> list[SearchDocument]:
        self.queries.append(query)
        if "MCP" in query or "开放平台" in query:
            return [
                SearchDocument(
                    query=query,
                    title="开发文档",
                    url="https://official.example/api",
                    content="公开法科公司提供法律API。",
                )
            ]
        return [
            SearchDocument(
                query=query,
                title="产品官网",
                url="https://official.example/product",
                content="公开法务助手由公开法科公司运营，是法律AI产品。",
            )
        ]


class _FallbackSearch(_RecordedSearch):
    def search(self, query: str, *, max_results: int = 5) -> list[SearchDocument]:
        self.queries.append(query)
        if len(self.queries) < 3:
            raise ProviderUnavailable("当前查询没有相关结果")
        return [
            SearchDocument(
                query=query,
                title="产品官网",
                url="https://official.example/product",
                content="公开法务助手由公开法科公司运营，是法律AI产品。",
            )
        ]


def test_external_search_runs_ecosystem_only_after_clear_identity() -> None:
    identity = _clear_result()
    identity["related_products"] = []
    identity["sources"].append(
        {
            "url": "https://official.example/product",
            "title": "产品官网",
            "source_type": "official_product",
            "supports": ["identity", "operator", "legal_ai_scope"],
        }
    )
    final = _clear_result()
    final["sources"].append(
        {
            "url": "https://official.example/product",
            "title": "产品官网",
            "source_type": "official_product",
            "supports": ["identity", "operator", "legal_ai_scope"],
        }
    )
    final["sources"].append(
        {
            "url": "https://hallucinated.example/mcp",
            "title": "不存在于搜索结果的MCP页面",
            "source_type": "official_docs",
            "supports": ["mcp"],
        }
    )
    final["related_products"].append(
        {
            "name": "未经搜索发现的MCP",
            "kind": "mcp",
            "relationship": "模型声称存在",
            "verification_status": "confirmed",
            "source_urls": ["https://hallucinated.example/mcp"],
        }
    )
    model = _SequenceModel([identity, final])
    search = _RecordedSearch()
    provider = ExternalSearchIdentityProvider(model, search)

    result = provider.research("公开法务助手")

    assert len(search.queries) == 7
    assert any("Skill 插件 连接器" in query for query in search.queries)
    assert len(model.prompts) == 2
    assert result.outcome == "clear"
    assert result.web_search_used is True
    assert {source.url for source in result.sources} == {
        "https://official.example/api",
        "https://official.example/product",
    }
    mcp = next(item for item in result.related_products if item.kind == "mcp")
    assert mcp.source_urls == []
    assert mcp.verification_status == "lead_only"


def test_external_search_stops_before_ecosystem_when_identity_is_ambiguous() -> None:
    ambiguous = _clear_result()
    ambiguous.update(
        {
            "outcome": "ambiguous",
            "canonical_product_name": None,
            "operator_name": None,
            "product_type": None,
            "is_legal_ai": None,
            "clarification_question": "请确认具体产品。",
            "candidates": [],
            "related_products": [],
        }
    )
    model = _SequenceModel([ambiguous])
    search = _RecordedSearch()

    result = ExternalSearchIdentityProvider(model, search).research("公开助手")

    assert result.outcome == "ambiguous"
    assert len(search.queries) == 4
    assert len(model.prompts) == 1
    assert result.related_products == []


def test_external_search_repairs_invalid_identity_contract_once() -> None:
    ambiguous = _clear_result()
    ambiguous.update(
        {
            "outcome": "ambiguous",
            "canonical_product_name": None,
            "operator_name": None,
            "product_type": None,
            "is_legal_ai": None,
            "clarification_question": "请确认具体产品。",
            "candidates": [],
            "related_products": [],
        }
    )
    model = _SequenceModel([{"outcome": "ambiguous"}, ambiguous])
    search = _RecordedSearch()

    result = ExternalSearchIdentityProvider(model, search).research("公开助手")

    assert result.outcome == "ambiguous"
    assert len(model.prompts) == 2
    assert "格式修复任务" in model.prompts[1]
    assert "不得增加公开证据中没有的事实" in model.prompts[1]


def test_external_search_continues_query_plan_after_irrelevant_results() -> None:
    ambiguous = _clear_result()
    ambiguous.update(
        {
            "outcome": "ambiguous",
            "canonical_product_name": None,
            "operator_name": None,
            "product_type": None,
            "is_legal_ai": None,
            "clarification_question": "请确认具体产品。",
            "candidates": [],
            "related_products": [],
        }
    )
    model = _SequenceModel([ambiguous])
    search = _FallbackSearch()

    result = ExternalSearchIdentityProvider(model, search).research("公开法务助手")

    assert result.outcome == "ambiguous"
    assert len(search.queries) == 4
    assert search.queries[0] == '"公开法务助手"'
    assert '"公开法务助手" 法律 AI 产品' in search.queries
    assert len(model.prompts) == 1
