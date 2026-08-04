from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from .models import Candidate


@dataclass(frozen=True)
class FixtureProduct:
    fixture_id: str
    product_name: str
    operator_name: str
    product_type: str
    is_legal_ai: bool
    aliases: tuple[str, ...] = ()
    related_product_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateDecision:
    outcome: Literal["clear", "ambiguous", "rejected"]
    message: str
    question: str | None = None
    product: FixtureProduct | None = None
    candidates: list[Candidate] = field(default_factory=list)


# These names are deliberately fictional. They test workflow behaviour and are not
# claims about real products or companies.
FIXTURES = {
    "衡法智研": FixtureProduct(
        fixture_id="fixture-hengfa-research",
        product_name="衡法智研",
        operator_name="衡法科技（测试主体）",
        product_type="法律AI研究助手（测试产品）",
        is_legal_ai=True,
        aliases=("衡法智研法律助手",),
        related_product_hints=("衡法开放平台 API（待后续公开核验）", "衡法法律知识库（待后续公开核验）"),
    ),
    "星云法律助手": FixtureProduct(
        fixture_id="fixture-xingyun-legal",
        product_name="星云法律助手",
        operator_name="星云法科（测试主体）",
        product_type="法律AI助手（测试产品）",
        is_legal_ai=True,
    ),
    "星云通用AI助手": FixtureProduct(
        fixture_id="fixture-xingyun-general",
        product_name="星云通用AI助手",
        operator_name="星云智能（测试主体）",
        product_type="通用AI助手（测试产品）",
        is_legal_ai=False,
    ),
    "晴空天气": FixtureProduct(
        fixture_id="fixture-qingkong-weather",
        product_name="晴空天气",
        operator_name="晴空网络（测试主体）",
        product_type="天气工具（测试产品）",
        is_legal_ai=False,
    ),
}

AMBIGUOUS_FIXTURES = {
    "星云助手": ("星云法律助手", "星云通用AI助手"),
}

GENERIC_TERMS = {
    "法律ai",
    "法律ai产品",
    "法律助手",
    "智能法律助手",
    "合同审查",
    "合同审查工具",
    "法律检索",
    "api",
    "mcp",
    "大模型",
}


def _fixture_for_name(name: str) -> FixtureProduct | None:
    for fixture in FIXTURES.values():
        if name == fixture.product_name or name in fixture.aliases:
            return fixture
    return None


def _candidate(product: FixtureProduct) -> Candidate:
    return Candidate(
        id=product.fixture_id,
        product_name=product.product_name,
        operator_name=product.operator_name,
        product_type=product.product_type,
        is_legal_ai=product.is_legal_ai,
    )


def evaluate_product_name(product_name: str) -> GateDecision:
    name = " ".join(product_name.split())
    fixture = _fixture_for_name(name)
    if fixture:
        if fixture.is_legal_ai:
            return GateDecision(
                outcome="clear",
                product=fixture,
                message="已由本地测试目录唯一识别法律AI产品。",
            )
        return GateDecision(
            outcome="rejected",
            product=fixture,
            message="该测试产品不属于法律AI产品，任务已按边界终止。",
        )

    if name in AMBIGUOUS_FIXTURES:
        choices = [_candidate(FIXTURES[item]) for item in AMBIGUOUS_FIXTURES[name]]
        return GateDecision(
            outcome="ambiguous",
            message="该名称可能对应多个不同产品，不能自动选择。",
            question="你具体想分析下面哪个产品？",
            candidates=choices,
        )

    lowered = name.casefold().replace(" ", "")
    has_multiple = bool(re.search(r"[/、]|还是|或者|或", name))
    if lowered in GENERIC_TERMS or has_multiple or len(name) < 3:
        return GateDecision(
            outcome="ambiguous",
            message="当前输入是泛称、功能描述或包含多个对象，无法唯一确认产品。",
            question="请提供确切的产品全称；如有重名，也可同时写明运营企业。",
        )

    return GateDecision(
        outcome="ambiguous",
        message="本地模拟身份目录没有该名称，不能用模型常识或名称相似度直接确认。",
        question="请确认确切产品全称；确认后，下一阶段仍会通过公开来源核验主体和产品边界。",
    )


def candidate_by_id(candidates: list[Candidate], candidate_id: str) -> Candidate | None:
    return next((item for item in candidates if item.id == candidate_id), None)
