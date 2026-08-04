from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from .identity_gate import evaluate_product_name
from .models import (
    Candidate,
    EvidenceSource,
    IdentityResearchResult,
    RelatedProduct,
)


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class ProviderInvalidResponse(RuntimeError):
    pass


class IdentityResearchProvider(Protocol):
    mode: str
    model_name: str | None

    @property
    def ready(self) -> bool: ...

    @property
    def readiness_message(self) -> str: ...

    def research(
        self,
        product_name: str,
        *,
        confirmed_by_user: bool = False,
        operator_hint: str | None = None,
    ) -> IdentityResearchResult: ...


@dataclass(frozen=True)
class OpenAIProviderSettings:
    api_key: str
    model: str = "gpt-5.6-luna"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls) -> "OpenAIProviderSettings":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("MODEL_CLASSIFIER", "gpt-5.6-luna").strip() or "gpt-5.6-luna",
            base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            timeout_seconds=float(os.getenv("TOOL_TIMEOUT_SECONDS", "90") or "90"),
        )


RESEARCH_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "outcome": {"type": "string", "enum": ["clear", "ambiguous", "rejected"]},
        "canonical_product_name": {"type": ["string", "null"]},
        "operator_name": {"type": ["string", "null"]},
        "product_type": {"type": ["string", "null"]},
        "is_legal_ai": {"type": ["boolean", "null"]},
        "clarification_question": {"type": ["string", "null"]},
        "candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "product_name": {"type": "string"},
                    "operator_name": {"type": ["string", "null"]},
                    "product_type": {"type": ["string", "null"]},
                    "is_legal_ai": {"type": ["boolean", "null"]},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "id",
                    "product_name",
                    "operator_name",
                    "product_type",
                    "is_legal_ai",
                    "source_urls",
                ],
            },
        },
        "related_products": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [
                            "product",
                            "api",
                            "mcp",
                            "model_platform",
                            "developer_platform",
                            "database",
                            "knowledge_base",
                            "agent",
                            "plugin",
                            "connector",
                            "skill",
                            "other",
                        ],
                    },
                    "relationship": {"type": "string"},
                    "verification_status": {
                        "type": "string",
                        "enum": ["confirmed", "lead_only", "not_publicly_verified"],
                    },
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "kind", "relationship", "verification_status", "source_urls"],
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "enum": [
                            "government",
                            "regulator",
                            "official_product",
                            "official_docs",
                            "official_terms",
                            "official_company",
                            "industry",
                            "research",
                            "media",
                            "other",
                        ],
                    },
                    "supports": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["identity", "operator", "legal_ai_scope", "ecosystem", "api", "mcp"],
                        },
                    },
                },
                "required": ["url", "title", "source_type", "supports"],
            },
        },
        "summary": {"type": "string"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "outcome",
        "canonical_product_name",
        "operator_name",
        "product_type",
        "is_legal_ai",
        "clarification_question",
        "candidates",
        "related_products",
        "sources",
        "summary",
        "limitations",
    ],
}


IDENTITY_SYSTEM_PROMPT = """你是法律AI产品身份研究Agent，只执行P2.2身份辨析与同企业AI生态线索识别。

必须遵守：
1. 只使用公开网页检索所得信息；优先级为政府/监管、产品官网与官方文档、官方条款和运营主体官网，再到可靠行业与媒体来源。
2. 不能只凭名称相似、搜索摘要、跳转关系或模型记忆认定产品、运营主体、法律AI属性或同企业关系。
3. clear 仅在产品唯一、运营主体和法律AI用途均有公开来源支持时使用。
4. 名称是泛称、简称、拼写不确定、对应多个对象或证据不足时使用 ambiguous；最多给3个候选，提出一个最小澄清问题。此时 related_products 必须为空。
5. rejected 仅在有公开证据表明所确认对象不是法律AI产品时使用；证据不足不能当作 rejected。
6. 只有 clear 时，才检索同一运营主体的其他AI相关产品，以及API、MCP、模型平台、开发平台、数据库、知识库、Agent、插件、连接器或Skill线索。
7. API、MCP、插件、连接器和Skill必须分开分类。只有官方明确称为MCP，或存在可核验的MCP服务端点、配置或使用文档，才能标记 kind=mcp；否则不得从API或插件推断MCP。
8. confirmed 需要对应公开来源；只有弱线索时标记 lead_only；未找到公开证据但需要说明时标记 not_publicly_verified。
9. 每条候选和关联项尽量附直接来源URL；sources要说明每个来源支持什么。不得捏造URL。
10. 不生成正式分析报告，不给法律意见，不建库，不训练，不请求登录，不访问付费或受限内容，不操作用户电脑。
11. 用户确认名称只代表指定研究对象，不替代公开核验。
12. 严格输出给定JSON结构，使用简体中文。"""


def _candidate_id(candidate: Candidate) -> str:
    raw = f"{candidate.product_name}|{candidate.operator_name or ''}".encode()
    return f"candidate-{sha256(raw).hexdigest()[:12]}"


def _normalize_result(result: IdentityResearchResult) -> IdentityResearchResult:
    result.candidates = [item.model_copy(update={"id": _candidate_id(item)}) for item in result.candidates[:3]]
    if result.outcome != "ambiguous":
        result.candidates = []
        result.clarification_question = None
    if result.outcome != "clear":
        result.related_products = []
    return result


def _response_output_text(
    payload: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], bool]:
    texts: list[str] = []
    annotations: list[dict[str, Any]] = []
    search_sources: list[dict[str, Any]] = []
    web_search_used = False
    for item in payload.get("output", []):
        if item.get("type") == "web_search_call":
            web_search_used = True
            action = item.get("action", {})
            if isinstance(action, dict) and isinstance(action.get("sources"), list):
                search_sources.extend(source for source in action["sources"] if isinstance(source, dict))
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
                annotations.extend(content.get("annotations", []))
    if not texts:
        raise ProviderInvalidResponse("Agent没有返回可解析的身份研究结果")
    return "".join(texts), annotations, search_sources, web_search_used


def _merge_citation_annotations(result: IdentityResearchResult, annotations: list[dict[str, Any]]) -> None:
    known = {source.url for source in result.sources}
    for annotation in annotations:
        citation = annotation.get("url_citation", annotation)
        url = citation.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")) or url in known:
            continue
        title = citation.get("title") if isinstance(citation.get("title"), str) else url
        result.sources.append(
            EvidenceSource(url=url, title=title, source_type="other", supports=["identity"])
        )
        known.add(url)


def _normalize_url(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/")


def _enforce_search_evidence(
    result: IdentityResearchResult,
    annotations: list[dict[str, Any]],
    search_sources: list[dict[str, Any]],
) -> None:
    visited = {
        _normalize_url(url)
        for url in [
            *(source.get("url") for source in search_sources),
            *(
                annotation.get("url_citation", annotation).get("url")
                for annotation in annotations
            ),
        ]
        if isinstance(url, str) and url.startswith(("http://", "https://"))
    }
    if visited:
        result.sources = [source for source in result.sources if _normalize_url(source.url) in visited]
        for candidate in result.candidates:
            candidate.source_urls = [url for url in candidate.source_urls if _normalize_url(url) in visited]
        for related in result.related_products:
            related.source_urls = [url for url in related.source_urls if _normalize_url(url) in visited]

    supported = {claim for source in result.sources for claim in source.supports}
    for related in result.related_products:
        required_claim = "mcp" if related.kind == "mcp" else "api" if related.kind == "api" else "ecosystem"
        supporting_urls = {
            _normalize_url(source.url) for source in result.sources if required_claim in source.supports
        }
        if related.verification_status == "confirmed" and not any(
            _normalize_url(url) in supporting_urls for url in related.source_urls
        ):
            related.verification_status = "lead_only"

    if result.outcome == "clear" and not {"identity", "operator", "legal_ai_scope"}.issubset(supported):
        attempted_name = result.canonical_product_name
        attempted_operator = result.operator_name
        attempted_type = result.product_type
        attempted_urls = [source.url for source in result.sources]
        result.outcome = "ambiguous"
        result.canonical_product_name = None
        result.operator_name = None
        result.product_type = None
        result.is_legal_ai = None
        result.clarification_question = "公开来源不足以同时确认产品、运营主体和法律AI用途；请补充确切全称或官方产品链接。"
        result.related_products = []
        if attempted_name:
            result.candidates = [
                Candidate(
                    id="pending",
                    product_name=attempted_name,
                    operator_name=attempted_operator,
                    product_type=attempted_type,
                    is_legal_ai=None,
                    source_urls=attempted_urls,
                )
            ]
        result.limitations.append("身份结论因缺少完整公开证据链而降级为待确认。")


class OpenAIResponsesIdentityProvider:
    mode = "openai_web_search"

    def __init__(
        self,
        settings: OpenAIProviderSettings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or OpenAIProviderSettings.from_env()
        self.model_name = self.settings.model
        self._transport = transport

    @property
    def ready(self) -> bool:
        return bool(self.settings.api_key)

    @property
    def readiness_message(self) -> str:
        if self.ready:
            return "真实公开检索已就绪；每次识别可能产生OpenAI API与网页检索费用。"
        return "未配置OPENAI_API_KEY；不会执行真实检索，也不会静默改用虚构结果。"

    def research(
        self,
        product_name: str,
        *,
        confirmed_by_user: bool = False,
        operator_hint: str | None = None,
    ) -> IdentityResearchResult:
        if not self.ready:
            raise ProviderNotConfigured(self.readiness_message)
        confirmation = "是" if confirmed_by_user else "否"
        user_prompt = (
            f"待辨析的产品名称：{product_name}\n"
            f"用户是否已从歧义候选中确认该名称：{confirmation}\n"
            f"候选运营主体提示：{operator_hint or '无'}\n"
            "请先完成唯一身份、运营主体与法律AI范围核验；仅在clear时继续同企业AI生态及API/MCP线索识别。"
        )
        body = {
            "model": self.settings.model,
            "store": False,
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.action.sources"],
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": IDENTITY_SYSTEM_PROMPT}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "legal_ai_identity_research",
                    "strict": True,
                    "schema": RESEARCH_JSON_SCHEMA,
                }
            },
        }
        try:
            with httpx.Client(
                base_url=self.settings.base_url,
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    "/responses",
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("公开检索超时；本次没有形成身份结论，请稍后重试") from exc
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                pass
            suffix = f"：{detail[:240]}" if detail else ""
            raise ProviderUnavailable(f"OpenAI身份检索调用失败（HTTP {exc.response.status_code}）{suffix}") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise ProviderUnavailable("无法连接真实身份检索服务；本次没有形成身份结论") from exc

        output_text, annotations, search_sources, web_search_used = _response_output_text(payload)
        try:
            result = IdentityResearchResult.model_validate(json.loads(output_text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ProviderInvalidResponse("Agent返回结果不符合P2.2身份研究契约") from exc
        result.web_search_used = web_search_used
        _merge_citation_annotations(result, annotations)
        _enforce_search_evidence(result, annotations, search_sources)
        return _normalize_result(result)


class FixtureIdentityResearchProvider:
    """Explicit offline provider for automated tests; never selected as a silent fallback."""

    mode = "deterministic_fixture"
    model_name = None
    ready = True
    readiness_message = "显式测试模式：使用虚构确定性数据，不代表真实公开检索。"

    def research(
        self,
        product_name: str,
        *,
        confirmed_by_user: bool = False,
        operator_hint: str | None = None,
    ) -> IdentityResearchResult:
        decision = evaluate_product_name(product_name)
        if decision.outcome == "clear":
            assert decision.product is not None
            related = [
                RelatedProduct(
                    name=item,
                    kind="other",
                    relationship="同一虚构测试主体的待核验线索",
                    verification_status="lead_only",
                )
                for item in decision.product.related_product_hints
            ]
            return IdentityResearchResult(
                outcome="clear",
                canonical_product_name=decision.product.product_name,
                operator_name=decision.product.operator_name,
                product_type=decision.product.product_type,
                is_legal_ai=True,
                clarification_question=None,
                candidates=[],
                related_products=related,
                sources=[],
                summary=decision.message,
                limitations=["虚构测试数据；没有执行真实公开检索。"],
            )
        if decision.outcome == "rejected":
            assert decision.product is not None
            return IdentityResearchResult(
                outcome="rejected",
                canonical_product_name=decision.product.product_name,
                operator_name=decision.product.operator_name,
                product_type=decision.product.product_type,
                is_legal_ai=False,
                clarification_question=None,
                candidates=[],
                related_products=[],
                sources=[],
                summary=decision.message,
                limitations=["虚构测试数据；没有执行真实公开检索。"],
            )
        return IdentityResearchResult(
            outcome="ambiguous",
            canonical_product_name=None,
            operator_name=None,
            product_type=None,
            is_legal_ai=None,
            clarification_question=decision.question,
            candidates=decision.candidates,
            related_products=[],
            sources=[],
            summary=decision.message,
            limitations=["虚构测试数据；没有执行真实公开检索。"],
        )


def provider_from_env() -> IdentityResearchProvider:
    mode = os.getenv("LEGAL_AGENT_IDENTITY_PROVIDER", "openai").strip().casefold()
    if mode == "fixture":
        return FixtureIdentityResearchProvider()
    if mode != "openai":
        raise ValueError("LEGAL_AGENT_IDENTITY_PROVIDER只能是openai或fixture")
    return OpenAIResponsesIdentityProvider()
