import json

import httpx
import pytest

from services.api.app.identity_provider import ExternalSearchIdentityProvider, provider_from_env
from services.api.app.model_provider import ChatCompletionsSettings, OpenAICompatibleJSONModel
from services.api.app.provider_errors import ProviderUnavailable
from services.api.app.search_provider import (
    BingRssTestSearchProvider,
    BingRssTestSearchSettings,
    TavilySearchProvider,
    TavilySearchSettings,
)


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
    assert captured["body"]["thinking"] == {"type": "disabled"}


def test_model_retries_one_empty_json_response() -> None:
    calls = 0
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        bodies.append(json.loads(request.content))
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
    assert len(bodies[0]["messages"]) == 2
    assert len(bodies[1]["messages"]) == 3
    assert "上次响应正文为空" in bodies[1]["messages"][-1]["content"]


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


def test_tavily_search_adapter_converts_site_filter_to_include_domains() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": []})

    search = TavilySearchProvider(
        TavilySearchSettings(api_key="tvly-secret", base_url="https://api.tavily.test"),
        transport=httpx.MockTransport(handler),
    )

    search.search('"测试产品" site:gov.cn')

    assert captured["body"]["include_domains"] == ["gov.cn"]

def test_bing_rss_test_search_preserves_exact_phrase_and_filters_unrelated_pages() -> None:
    captured_query = ""
    official_html = (
        "<html><head><title>产品官网</title></head><body>"
        + ("得理法搜是法律AI产品。" * 30)
        + "</body></html>"
    )
    unrelated_html = (
        "<html><head><title>公开的释义</title></head><body>"
        + ("汉语字典与语文教学内容。" * 30)
        + "</body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_query
        if request.url.path == "/search":
            captured_query = request.url.params["q"]
            rss = """<?xml version="1.0"?><rss><channel>
              <item><title>公开怎么读</title><link>https://dictionary.example/public</link></item>
              <item><title>产品官网</title><link>https://official.example/product</link></item>
              <item><title>内网</title><link>http://127.0.0.1/private</link></item>
            </channel></rss>"""
            return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"})
        if request.url.host == "dictionary.example":
            return httpx.Response(
                200,
                text=unrelated_html,
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if request.url.host == "official.example":
            return httpx.Response(
                200,
                text=official_html,
                headers={"content-type": "text/html; charset=utf-8"},
            )
        return httpx.Response(404)

    provider = BingRssTestSearchProvider(
        BingRssTestSearchSettings(base_url="https://cn.bing.test"),
        transport=httpx.MockTransport(handler),
    )
    documents = provider.search('"得理法搜" 法律 AI')

    assert '"得理法搜"' in captured_query
    assert provider.search_tier == "test_only"
    assert [item.url for item in documents] == ["https://official.example/product"]
    assert documents[0].score == 3.0
    assert documents[0].retrieval_status == "direct_page"
    assert "得理法搜是法律AI产品" in documents[0].content


def test_bing_rss_test_search_fails_closed_when_pages_cannot_be_read() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                text=(
                    "<?xml version='1.0'?><rss><channel><item><title>产品</title>"
                    "<link>https://blocked.example/product</link></item></channel></rss>"
                ),
            )
        return httpx.Response(403)

    provider = BingRssTestSearchProvider(
        BingRssTestSearchSettings(base_url="https://cn.bing.test"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderUnavailable, match="不会使用模型记忆补造证据"):
        provider.search("公开法务助手")


def test_bing_rss_test_search_skips_one_page_connection_failure() -> None:
    official_html = "<html><body>" + ("得理法搜是法律AI产品。" * 30) + "</body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                text=(
                    "<?xml version='1.0'?><rss><channel>"
                    "<item><title>失效候选</title><link>https://dead.example/product</link></item>"
                    "<item><title>得理法搜官网</title>"
                    "<link>https://official.example/product</link></item>"
                    "</channel></rss>"
                ),
            )
        if request.url.host == "dead.example":
            raise httpx.ConnectError("candidate page is unreachable", request=request)
        if request.url.host == "official.example":
            return httpx.Response(
                200,
                text=official_html,
                headers={"content-type": "text/html; charset=utf-8"},
            )
        return httpx.Response(404)

    provider = BingRssTestSearchProvider(
        BingRssTestSearchSettings(base_url="https://cn.bing.test"),
        transport=httpx.MockTransport(handler),
    )

    documents = provider.search('"得理法搜" 法律 AI')

    assert [item.url for item in documents] == ["https://official.example/product"]


def test_bing_rss_test_search_distinguishes_unreadable_pages_from_search_outage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                text=(
                    "<?xml version='1.0'?><rss><channel><item><title>候选</title>"
                    "<link>https://dead.example/product</link></item></channel></rss>"
                ),
            )
        raise httpx.ConnectError("candidate page is unreachable", request=request)

    provider = BingRssTestSearchProvider(
        BingRssTestSearchSettings(base_url="https://cn.bing.test"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderUnavailable, match="Bing搜索入口正常.*候选网页均无法直接读取"):
        provider.search('"得理法搜" 法律 AI')


def test_keyless_search_falls_back_to_exact_official_app_catalog_record() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cn.bing.test" and request.url.path == "/search":
            return httpx.Response(200, text="<?xml version='1.0'?><rss><channel /></rss>")
        if request.url.host == "itunes.apple.test":
            assert request.url.params["term"] == "得理法搜"
            return httpx.Response(
                200,
                json={
                    "resultCount": 3,
                    "results": [
                        {
                            "trackName": "得理法搜",
                            "sellerName": "Shenzhen Deli Technology Co., Ltd.",
                            "trackViewUrl": "https://apps.apple.com/cn/app/id1512357117",
                            "description": "得理法搜是深圳得理科技有限公司推出的法律AI产品。",
                        },
                        {
                            "trackName": "得理律助",
                            "sellerName": "Shenzhen Deli Technology Co., Ltd.",
                            "trackViewUrl": "https://apps.apple.com/cn/app/id-other",
                            "description": "律师办公应用。",
                        },
                        {
                            "trackName": "无关法律应用",
                            "sellerName": "Other Developer",
                            "trackViewUrl": "https://apps.apple.com/cn/app/id-unrelated",
                            "description": "无关内容。",
                        },
                    ],
                },
            )
        return httpx.Response(404)

    provider = BingRssTestSearchProvider(
        BingRssTestSearchSettings(
            base_url="https://cn.bing.test",
            app_catalog_url="https://itunes.apple.test/search",
        ),
        transport=httpx.MockTransport(handler),
    )

    documents = provider.search('"得理法搜" 法律 AI')

    assert [item.title for item in documents] == ["Apple App Store：得理法搜"]
    assert documents[0].retrieval_status == "official_app_catalog"
    assert "Shenzhen Deli Technology Co., Ltd." in documents[0].content
    assert "得理律助" not in documents[0].content


def test_deepseek_default_requires_no_search_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGAL_AGENT_IDENTITY_PROVIDER", "deepseek")
    monkeypatch.delenv("LEGAL_AGENT_SEARCH_PROVIDER", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    provider = provider_from_env()

    assert isinstance(provider, ExternalSearchIdentityProvider)
    assert provider.ready is True
    assert provider.model_provider_name == "deepseek"
    assert provider.search_provider_name == "keyless_test_search"
    assert provider.search_tier == "test_only"
    assert "测试级" in provider.readiness_message


def test_legacy_bing_search_setting_enables_keyless_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGAL_AGENT_IDENTITY_PROVIDER", "deepseek")
    monkeypatch.setenv("LEGAL_AGENT_SEARCH_PROVIDER", "bing_rss_test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    provider = provider_from_env()

    assert provider.search_provider_name == "keyless_test_search"
