from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlparse

from .identity_provider import ExternalSearchIdentityProvider, FixtureIdentityResearchProvider
from .model_provider import StructuredModelProvider, generate_validated_json
from .models import (
    ReportDraft,
    ReportInsightDraft,
    ReportSectionDraft,
    ReportSourceRecord,
    Task,
)
from .provider_errors import ProviderInvalidResponse, ProviderNotConfigured, ProviderUnavailable
from .search_provider import PublicSearchProvider, SearchDocument


REPORT_SECTION_HEADINGS = [
    "一、企业发展历程与核心驱动（对标维度1：发展积淀与战略演进）",
    "二、企业经营情况（对标维度2：经营质量与增长质量）",
    "三、企业业务版块（对标维度3：业务矩阵与核心赛道）",
    "四、企业行业势能（对标维度4：行业地位与竞争壁垒）",
    "五、企业市场布局（对标维度5：市场版图与核心客户）",
]


REPORT_SYSTEM_PROMPT = """你是法律AI产品标杆分析报告起草Agent，只执行P2.3.3主张—证据绑定测试稿生成。

必须遵守：
1. 只使用用户任务卡片和本轮实际检索证据，不得使用模型记忆补充产品、企业、价格、客户、融资、功能、团队或市场事实，不得捏造URL。
2. 参考报告只决定五个对标维度、报告摘要和洞察总结的结构，不是事实来源。
3. 严格区分已核实事实、企业公开声明和分析判断；企业自述使用“官网称”“应用说明显示”等归因措辞。
4. 公开证据不足时缩短对应章节并明确“公开资料不足以证明”，不得为了完整度补造数据。
5. 不新增实名竞品、统一评分、TAM/SAM/SOM、收入预测、估值或投资判断。
6. 同企业AI产品、API、MCP、插件、连接器和Skill必须分层。只有官方明确MCP或存在端点、配置、文档时才能写已确认MCP。
7. 经营、客户、融资、技术准确性和安全能力没有直接证据时不得作强结论；不得把上线、宣传或应用商店记录写成规模化商业验证。
7.1 不得把备案、联合研发、产品上线、数据规模自述或定价梯度直接写成“壁垒”“成熟变现”“市场认可”“付费意愿”或领先地位。收费套餐只能证明设置了收费渠道，不能证明形成收入或变现能力。
7.2 研发起点早于公司成立时间不构成逻辑矛盾，可能来自前身团队、实验室或成立前研发；没有直接证据不得据此写“工商信息脱节”“影响公信力”。
7.3 备案结论必须引用政府或监管公开记录；只有企业官网或应用商店自述时，必须写“企业公开资料称”，不得写成监管事实。
8. 洞察总结形成“企业特有机制或矛盾—事实依据—约束条件—业务含义”闭环，控制在4至6条；证据不足时可以少于4条。
9. executive_summary_source_urls、每个section.source_urls和每个insight.source_urls都必须填写支持相应主张的实际证据URL；不得仅生成总来源清单而让正文无引用。URL只能来自证据中实际出现的值。
10. 不提供个案法律意见，不把测试稿表述为审计、投资、尽调或法律意见。
11. 使用简体中文，只输出符合给定结构的JSON对象，不输出Markdown或额外说明。"""


class ReportDraftProvider(Protocol):
    @property
    def ready(self) -> bool: ...

    def generate(self, task: Task) -> ReportDraft: ...


def _normalize_url(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/")


def _dedupe_documents(documents: list[SearchDocument], limit: int = 18) -> list[SearchDocument]:
    kept: list[SearchDocument] = []
    seen: set[str] = set()
    for document in documents:
        key = _normalize_url(document.url)
        if key in seen:
            continue
        seen.add(key)
        kept.append(document)
        if len(kept) >= limit:
            break
    return kept


def _source_classification(url: str, source_type: str) -> tuple[str, str]:
    host = (urlparse(url).hostname or "").lower()
    if host in {"apps.apple.com", "sj.qq.com", "appgallery.huawei.com"}:
        return "platform_listing", "platform_listing"
    if source_type in {"government", "regulator"} or host.endswith(".gov.cn"):
        return source_type, "government_record"
    if host.endswith(".ac.cn"):
        return "research_institution", "research_institution"
    if source_type.startswith("official_"):
        return source_type, "official_primary"
    if source_type in {"industry", "research", "media"}:
        return source_type, "independent_secondary"
    return source_type, "other_public"


def _moderate_claim_strength(text: str) -> str:
    replacements = {
        "8年研发与公司成立时间存在矛盾": "研发起点与公司成立时间采用不同口径，公开资料不足以确定二者关系",
        "8年研发与成立时间存在矛盾": "研发起点与公司成立时间采用不同口径，公开资料不足以确定二者关系",
        "宣传口径与工商信息脱节": "不同公开页面的时间口径尚未统一",
        "影响公信力": "需要进一步区分研发团队历史与公司存续时间",
        "行业势能存在虚高可能": "公开证据不足以独立评价其行业势能",
        "表明具备变现能力": "表明其已设置收费渠道",
        "说明产品具备变现能力": "说明产品已设置收费渠道",
        "行业领先地位": "行业位置",
        "国内领先地位": "市场位置",
        "付费意愿已经得到证明": "收费尝试已公开呈现，但实际付费意愿尚待验证",
        "付费意愿已得到证明": "收费尝试已公开呈现，但实际付费意愿尚待验证",
        "构成数据与模型壁垒": "可能形成数据与模型方面的差异化基础",
        "形成数据与模型壁垒": "可能形成数据与模型方面的差异化基础",
        "已形成壁垒": "呈现出一定差异化基础",
        "形成可信壁垒": "可能形成可信度基础",
        "构成可信壁垒": "可能形成可信度基础",
        "成熟的变现路径": "初步的收费路径",
        "成熟变现路径": "初步收费路径",
        "证明B端付费意愿": "显示其正在尝试B端收费",
        "显示B端付费意愿": "显示其正在尝试B端收费",
        "高增长已验证": "增长情况尚待公开数据验证",
        "国内领先": "具有一定市场辨识度",
        "行业领先": "具有一定行业辨识度",
        "行业第一": "行业位置仍待公开数据验证",
    }
    for strong, moderate in replacements.items():
        text = text.replace(strong, moderate)
    return text


def _moderate_regulatory_claim(text: str, *, has_regulatory_source: bool) -> str:
    if has_regulatory_source:
        return text
    replacements = {
        "得理法律大模型为首批通过国家网信办备案的生成式算法之一": "企业公开资料称得理法律大模型已完成相关备案，但本次未取得监管名单的直接对应记录",
        "得理法律大模型通过网信办备案": "企业公开资料称得理法律大模型已完成相关备案，但本次未取得监管名单的直接对应记录",
        "得理法律大模型通过国家网信办备案": "企业公开资料称得理法律大模型已完成相关备案，但本次未取得监管名单的直接对应记录",
    }
    for strong, moderate in replacements.items():
        text = text.replace(strong, moderate)
    text = re.sub(
        r"([^。；，]{1,50})(?:为|是)首批通过国家网信办备案的生成式算法之一",
        r"据企业公开资料称，\1较早完成相关备案；本次未取得监管名单的直接对应记录",
        text,
    )
    text = re.sub(
        r"([^。；，]{1,50})通过(?:国家)?网信办备案",
        r"据企业公开资料称，\1已完成相关备案；本次未取得监管名单的直接对应记录",
        text,
    )
    return text


def _citation_gaps(draft: ReportDraft, allowed_urls: set[str] | None = None) -> list[str]:
    def has_valid_url(urls: list[str]) -> bool:
        if allowed_urls is None:
            return bool(urls)
        return any(_normalize_url(url) in allowed_urls for url in urls)

    gaps: list[str] = []
    if not has_valid_url(draft.executive_summary_source_urls):
        gaps.append("报告摘要")
    for index, section in enumerate(draft.sections, start=1):
        placeholder = section.paragraphs == ["当前公开证据不足以形成可靠结论。"]
        if not placeholder and not has_valid_url(section.source_urls):
            gaps.append(f"主体章节{index}")
    for index, insight in enumerate(draft.insights, start=1):
        if not has_valid_url(insight.source_urls):
            gaps.append(f"洞察{index}")
    return gaps


class EvidenceBoundReportDraftProvider:
    def __init__(self, model: StructuredModelProvider, search: PublicSearchProvider) -> None:
        self.model = model
        self.search = search

    @property
    def ready(self) -> bool:
        return self.model.ready and self.search.ready

    def _collect_documents(self, task: Task) -> list[SearchDocument]:
        product = task.canonical_product_name or task.submitted_product_name
        operator = task.operator_name or product
        queries = [
            f'"{product}" 官网 产品 功能 服务',
            f'"{product}" 价格 套餐 用户协议 隐私政策',
            f'"{operator}" 官网 AI 产品 开放平台 API',
            f'"{operator}" 融资 客户 合作 案例',
            f'"{operator}" MCP 官方 文档',
            f'"{product}" 备案号 上线编号 官方',
            f'"{operator}" 生成式人工智能 备案 算法',
            f'"{operator}" 科研院所 联合实验室 法律人工智能',
        ]
        documents: list[SearchDocument] = []
        failures: list[str] = []
        for query in queries:
            try:
                documents.extend(self.search.search(query, max_results=5))
            except ProviderUnavailable as exc:
                failures.append(str(exc))
        deduplicated = _dedupe_documents(documents)
        if not deduplicated:
            detail = failures[-1] if failures else "没有取得公开证据"
            raise ProviderUnavailable(
                f"报告研究没有取得可直接使用的公开证据：{detail}；不会使用模型记忆补写报告"
            )
        return deduplicated

    @staticmethod
    def _context(task: Task, documents: list[SearchDocument]) -> str:
        task_payload = {
            "product_name": task.canonical_product_name or task.submitted_product_name,
            "operator_name": task.operator_name,
            "product_type": task.product_type,
            "identity_summary": task.research_summary,
            "related_products": [item.model_dump(mode="json") for item in task.related_products],
            "identity_sources": [item.model_dump(mode="json") for item in task.sources],
            "identity_limitations": task.limitations,
        }
        evidence_payload = [
            {
                "query": item.query,
                "title": item.title,
                "url": item.url,
                "content_excerpt": item.content[:1800],
                "retrieval_status": item.retrieval_status,
            }
            for item in documents
        ]
        return json.dumps(
            {"task_card": task_payload, "public_evidence": evidence_payload},
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _enforce_evidence(
        draft: ReportDraft,
        documents: list[SearchDocument],
        task: Task,
    ) -> ReportDraft:
        by_url = {_normalize_url(item.url): item for item in documents}
        identity_by_url = {_normalize_url(item.url): item for item in task.sources}
        allowed_urls = set(by_url) | set(identity_by_url)
        evidence_levels: dict[str, str] = {}
        for normalized_url in allowed_urls:
            identity_source = identity_by_url.get(normalized_url)
            source_type = identity_source.source_type if identity_source else "other"
            url = identity_source.url if identity_source else by_url[normalized_url].url
            _, evidence_levels[normalized_url] = _source_classification(url, source_type)
        used: set[str] = set()
        for section in draft.sections:
            section.source_urls = [
                url
                for url in section.source_urls
                if _normalize_url(url) in allowed_urls
            ]
            used.update(_normalize_url(url) for url in section.source_urls)
            has_regulatory_source = any(
                evidence_levels.get(_normalize_url(url)) == "government_record"
                for url in section.source_urls
            )
            section.paragraphs = [
                _moderate_regulatory_claim(
                    _moderate_claim_strength(item),
                    has_regulatory_source=has_regulatory_source,
                )
                for item in section.paragraphs
            ]
            section.key_points = [
                _moderate_regulatory_claim(
                    _moderate_claim_strength(item),
                    has_regulatory_source=has_regulatory_source,
                )
                for item in section.key_points
            ]
        for insight in draft.insights:
            insight.source_urls = [
                url
                for url in insight.source_urls
                if _normalize_url(url) in allowed_urls
            ]
            used.update(_normalize_url(url) for url in insight.source_urls)
            has_regulatory_source = any(
                evidence_levels.get(_normalize_url(url)) == "government_record"
                for url in insight.source_urls
            )
            insight.title = _moderate_claim_strength(insight.title)
            insight.analysis = _moderate_regulatory_claim(
                _moderate_claim_strength(insight.analysis),
                has_regulatory_source=has_regulatory_source,
            )

        draft.executive_summary_source_urls = [
            url
            for url in draft.executive_summary_source_urls
            if _normalize_url(url) in allowed_urls
        ]
        used.update(_normalize_url(url) for url in draft.executive_summary_source_urls)
        summary_has_regulatory_source = any(
            evidence_levels.get(_normalize_url(url)) == "government_record"
            for url in draft.executive_summary_source_urls
        )
        draft.executive_summary = [
            _moderate_regulatory_claim(
                _moderate_claim_strength(item),
                has_regulatory_source=summary_has_regulatory_source,
            )
            for item in draft.executive_summary
        ]

        gaps = _citation_gaps(draft)
        if gaps:
            raise ProviderInvalidResponse(
                "报告主张未绑定有效来源（" + "、".join(gaps) + "），已拒绝生成Word"
            )

        # The ecosystem table is part of the report. Its identity-stage evidence must
        # travel with it even when the report-stage search does not rediscover the page.
        ecosystem_urls = {
            _normalize_url(url)
            for item in task.related_products
            for url in item.source_urls
            if _normalize_url(url) in allowed_urls
        }
        used.update(ecosystem_urls)
        if not used:
            raise ProviderInvalidResponse("报告草稿没有引用任何实际检索来源，已拒绝生成Word")
        accessed_at = datetime.now(UTC).date().isoformat()
        records: list[ReportSourceRecord] = []
        for normalized_url in used:
            identity_source = identity_by_url.get(normalized_url)
            document = by_url.get(normalized_url)
            if identity_source:
                source_type, evidence_level = _source_classification(
                    identity_source.url,
                    identity_source.source_type,
                )
                records.append(
                    ReportSourceRecord(
                        url=identity_source.url,
                        title=identity_source.title,
                        retrieval_status="identity_stage_verified",
                        source_type=source_type,
                        evidence_level=evidence_level,
                        accessed_at=accessed_at,
                        inherited_from_identity=True,
                    )
                )
            elif document:
                source_type, evidence_level = _source_classification(document.url, "other")
                records.append(
                    ReportSourceRecord(
                        url=document.url,
                        title=document.title,
                        retrieval_status=document.retrieval_status,
                        source_type=source_type,
                        evidence_level=evidence_level,
                        accessed_at=accessed_at,
                    )
                )
        records.sort(key=lambda item: (item.evidence_level, item.title, item.url))
        draft.sources = records
        return draft

    def generate(self, task: Task) -> ReportDraft:
        if not self.ready:
            raise ProviderNotConfigured("报告生成所需模型或搜索组件未就绪")
        documents = self._collect_documents(task)
        schema = json.dumps(ReportDraft.model_json_schema(), ensure_ascii=False)
        prompt = f"""请为已通过身份闸门的法律AI产品制作P2.3.3本地Word测试稿。

五个主体章节必须按以下顺序组织；证据不足时保留标题但缩短内容并说明边界：
{json.dumps(REPORT_SECTION_HEADINGS, ensure_ascii=False)}

长度要求：executive_summary写2至3条；每个主体章节只写1个不超过220字的paragraph、最多2个短key_points；insights写2至3条且每条analysis不超过180字。摘要、每个实际内容章节和每条洞察必须分别填写支持它们的source_urls。必须优先保证JSON完整闭合，不得为了篇幅扩写。sources必须输出空数组，系统会依据有效引用自动回填。

任务卡片与实际公开证据：
{self._context(task, documents)}

输出JSON必须符合以下Schema：
{schema}
"""
        draft = generate_validated_json(
            self.model,
            REPORT_SYSTEM_PROMPT,
            prompt,
            ReportDraft,
            contract_name="模型返回内容不符合P2.3.3报告草稿契约",
        )
        allowed_urls = {
            _normalize_url(item.url) for item in documents
        } | {
            _normalize_url(item.url) for item in task.sources
        }
        gaps = _citation_gaps(draft, allowed_urls)
        if gaps:
            repair_prompt = f"""引用修复任务：上一版结构有效，但以下部分没有绑定来源：{json.dumps(gaps, ensure_ascii=False)}。

请保持原有事实边界和篇幅，只为摘要、每个实际内容章节和每条洞察补充能够直接支持相应主张的source_urls；若证据不能支持原主张，应降低或删除该主张，不得猜测URL。sources仍输出空数组。

上一版草稿：
{json.dumps(draft.model_dump(mode="json", exclude={"sources"}), ensure_ascii=False)}

任务卡片与实际公开证据：
{self._context(task, documents)}

输出JSON必须符合以下Schema：
{schema}
"""
            draft = generate_validated_json(
                self.model,
                REPORT_SYSTEM_PROMPT,
                repair_prompt,
                ReportDraft,
                contract_name="模型未完成P2.3.3主张—证据绑定修复",
            )
            remaining_gaps = _citation_gaps(draft, allowed_urls)
            if remaining_gaps:
                raise ProviderInvalidResponse(
                    "模型未完成主张—证据绑定（"
                    + "、".join(remaining_gaps)
                    + "），已停止生成Word"
                )
        product = task.canonical_product_name or task.submitted_product_name
        draft.report_title = f"{product}标杆分析报告"
        draft.report_subtitle = "法律科技赛道 · P2.3.3主张—证据绑定测试稿"
        draft.sections = draft.sections[:5]
        while len(draft.sections) < 5:
            draft.sections.append(
                ReportSectionDraft(
                    paragraphs=["当前公开证据不足以形成可靠结论。"],
                    key_points=["本维度暂不作强判断。"],
                )
            )
        for heading, section in zip(REPORT_SECTION_HEADINGS, draft.sections, strict=True):
            section.heading = heading
        if self.search.search_tier == "test_only":
            limitation = "本稿使用免费测试级公开检索，证据覆盖和稳定性不足以支持正式对外发布。"
            if limitation not in draft.limitations:
                draft.limitations.append(limitation)
        return self._enforce_evidence(draft, documents, task)


class FixtureReportDraftProvider:
    ready = True

    def generate(self, task: Task) -> ReportDraft:
        product = task.canonical_product_name or task.submitted_product_name
        source_url = "https://example.invalid/fixture-source"
        sections = [
            ReportSectionDraft(
                heading=heading,
                paragraphs=[f"{product}的本段内容来自虚构自动化测试数据，不代表真实产品结论。"],
                key_points=["仅验证报告生成、版式和下载链路。"],
                source_urls=[source_url],
            )
            for heading in REPORT_SECTION_HEADINGS
        ]
        draft = ReportDraft(
            report_title=f"{product}标杆分析报告",
            report_subtitle="法律科技赛道 · P2.3.3虚构测试稿",
            executive_summary=["本报告仅用于自动化测试，不包含真实企业事实。"],
            sections=sections,
            insights=[
                ReportInsightDraft(
                    title="测试闭环已形成",
                    analysis="身份确认后可以生成并下载Word文件；该结论只描述测试链路。",
                    source_urls=[source_url],
                )
            ],
            limitations=["虚构测试数据；不得作为真实报告使用。"],
        )
        # ReportDraft deliberately ignores model-supplied ledgers. The trusted
        # fixture ledger is therefore attached only after schema construction.
        draft.sources = [
            ReportSourceRecord(
                url=source_url,
                title="虚构自动化测试来源",
                retrieval_status="fixture",
                evidence_level="test_fixture",
            )
        ]
        draft.executive_summary_source_urls = [source_url]
        return draft


class UnavailableReportDraftProvider:
    ready = False

    def generate(self, task: Task) -> ReportDraft:
        raise ProviderNotConfigured("当前身份适配器尚未实现P2.3.3报告生成")


def report_provider_from_identity(identity_provider) -> ReportDraftProvider:
    if isinstance(identity_provider, ExternalSearchIdentityProvider):
        return EvidenceBoundReportDraftProvider(identity_provider.model, identity_provider.search)
    if isinstance(identity_provider, FixtureIdentityResearchProvider):
        return FixtureReportDraftProvider()
    return UnavailableReportDraftProvider()
