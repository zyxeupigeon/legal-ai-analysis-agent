import json

import httpx

from services.api.app.model_provider import ChatCompletionsSettings, OpenAICompatibleJSONModel
from services.api.app.search_provider import TavilySearchProvider, TavilySearchSettings


def test_openai_compatible_model_uses_json_chat_completions_contract() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"outcome":"ambiguous"}'}}]},
        )

    model = OpenAICompatibleJSONModel(
        ChatCompletionsSettings(
            provider_name="deepseek",
            api_key_name="DEEPSEEK_API_KEY",
            api_key="secret",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.test",
        ),
        transport=httpx.MockTransport(handler),
    )
    output = model.generate_json("输出JSON", "测试")

    assert json.loads(output)["outcome"] == "ambiguous"
    assert captured["path"] == "/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["model"] == "deepseek-v4-flash"
    assert captured["body"]["stream"] is False


def test_model_retries_one_empty_json_response() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = "" if calls == 1 else '{"ok":true}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    model = OpenAICompatibleJSONModel(
        ChatCompletionsSettings(
            provider_name="deepseek",
            api_key_name="DEEPSEEK_API_KEY",
            api_key="secret",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.test",
            max_retries=1,
        ),
        transport=httpx.MockTransport(handler),
    )

    assert json.loads(model.generate_json("JSON", "测试"))["ok"] is True
    assert calls == 2


def test_tavily_search_adapter_returns_only_http_documents() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "产品官网",
                        "url": "https://official.example/product",
                        "content": "法律AI产品介绍",
                        "score": 0.9,
                    },
                    {"title": "无效", "url": "javascript:alert(1)", "content": "无效"},
                ]
            },
        )

    search = TavilySearchProvider(
        TavilySearchSettings(api_key="tvly-secret", base_url="https://api.tavily.test"),
        transport=httpx.MockTransport(handler),
    )
    documents = search.search("测试查询")

    assert captured["authorization"] == "Bearer tvly-secret"
    assert captured["body"]["search_depth"] == "basic"
    assert captured["body"]["include_raw_content"] is False
    assert [item.url for item in documents] == ["https://official.example/product"]
