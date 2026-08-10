from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlparse

from .identity_provider import ExternalSearchIdentityProvider, FixtureIdentityResearchProvider
from .model_provider import StructuredModelProvider, generate_validated_json
from .models import (
    CitationAuditResult,
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


REPORT_SYSTEM_PROMPT = """你是法律AI产品标杆分析报告起草Agent，只执行P2.3.4证据相关性与冲突处理测试稿生成。

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
9.1 同一段包含多个事实时，所列来源合计必须直接支持其中每项重要事实；只与产品名称相关但不支持具体主张的网页不得引用。
9.2 API、MCP、插件、连接器和Skill分别判断。发现Skill不能写成MCP；发现API不能推定存在插件、连接器或MCP。
9.3 不同来源的研发年限、实验室成立年份、公司成立年份等口径不同，不得强行合并；应说明口径差异和目前能确认的范围。
10. 不提供个案法律意见，不把测试稿表述为审计、投资、尽调或法律意见。
11. 使用简体中文，只输出符合给定结构的JSON对象，不输出Markdown或额外说明。"""


class ReportDraftProvider(Protocol):
    @property
    def ready(self) -> bool: ...

    def generate(self, task: Task) -> ReportDraft: ...


def _normalize_url(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/")


def _dedupe_documents(documents: list[SearchDocument], limit: int = 28) -> list[SearchDocument]:
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
    claim_pattern = re.compile(r"(?:首批.{0,12})?(?:通过|完成).{0,12}(?:网信办|备案)|首批.{0,24}备案")
    sentences = re.findall(r"[^。！？]+[。！？]?", text)
    rewritten: list[str] = []
    for sentence in sentences:
        if not claim_pattern.search(sentence):
            rewritten.append(sentence)
            continue
        subjects = re.findall(r"[\u4e00-\u9fffA-Za-z0-9·-]{2,24}(?:大模型|算法|服务)", sentence)
        subject = subjects[-1] if subjects else "相关模型或算法"
        rewritten.append(
            f"企业公开资料称{subject}已完成相关备案，但本次未取得监管公开名单的直接对应记录。"
        )
    return "".join(rewritten) or text


def _timeline_conflict_note(documents: list[SearchDocument]) -> str | None:
    combined = "\n".join(item.content for item in documents)
    durations = list(dict.fromkeys(re.findall(r"历经\s*(\d{1,2})\s*年", combined)))
    if len(durations) > 1:
        quoted = "、".join(f"“历经{duration}年”" for duration in durations)
        return (
            f"公开材料存在研发年限口径差异：不同来源分别使用{quoted}的表述；"
            "目前无法确认各自起算点，不能强行合并为同一时间线。"
        )
    founded_match = re.search(
        r"(20\d{2})年[^。\n]{0,80}(?:(?:联合实验室|实验室)[^。\n]{0,20}(?:成立|共建)|(?:成立|共建)[^。\n]{0,40}(?:联合实验室|实验室))",
        combined,
    )
    if not durations or not founded_match:
        return None
    return (
        f"公开材料存在时间口径差异：部分产品说明称“历经{durations[0]}年研发”，"
        f"另有机构公开资料记载相关联合实验室于{founded_match.group(1)}年成立；二者可能分别指团队研发历史与实验室存续时间，不能直接视为矛盾或相互替代。"
    )


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
            f'"{operator}" 联合实验室 site:ac.cn',
            f'"{product}" 历经 年 研发',
            f'"{operator}" 研发 年限 site:gov.cn',
            f'"{operator}" 开放平台 API Skill 插件 连接器 MCP',
            f'"{product}" "{operator}" 备案 site:cac.gov.cn',
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
                documents.extend(self.search.search(query, max_results=3)[:3])
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
    def _audit_targets(draft: ReportDraft) -> list[dict[str, object]]:
        targets: list[dict[str, object]] = []
        for index, summary in enumerate(draft.executive_summary, start=1):
            targets.append(
                {
                    "target_id": f"summary:{index}",
                    "text": summary,
                    "candidate_urls": draft.executive_summary_source_urls,
                }
            )
        for index, section in enumerate(draft.sections, start=1):
            if section.paragraphs == ["当前公开证据不足以形成可靠结论。"]:
                continue
            targets.append(
                {
                    "target_id": f"section:{index}",
                    "text": " ".join(section.paragraphs + section.key_points),
                    "candidate_urls": section.source_urls,
                }
            )
        for index, insight in enumerate(draft.insights, start=1):
            targets.append(
                {
                    "target_id": f"insight:{index}",
                    "text": f"{insight.title}：{insight.analysis}",
                    "candidate_urls": insight.source_urls,
                }
            )
        return targets

    def _audit_citations(
        self,
        draft: ReportDraft,
        documents: list[SearchDocument],
        task: Task,
    ) -> tuple[CitationAuditResult, list[str]]:
        targets = self._audit_targets(draft)
        schema = json.dumps(CitationAuditResult.model_json_schema(), ensure_ascii=False)
        candidate_urls = {
            _normalize_url(url)
            for target in targets
            for url in target["candidate_urls"]
        }
        candidate_documents = [
            item for item in documents if _normalize_url(item.url) in candidate_urls
        ]
        candidate_identity_sources = [
            item.model_dump(mode="json")
            for item in task.sources
            if _normalize_url(item.url) in candidate_urls
        ]
        evidence_payload = [
            {
                "title": item.title,
                "url": item.url,
                "content_excerpt": item.content[:1800],
                "retrieval_status": item.retrieval_status,
            }
            for item in candidate_documents
        ]
        prompt = f"""证据相关性审计：逐项判断候选URL是否直接支持目标文本中的重要事实。

规则：
1. 只有来源正文直接支持目标中的具体事实，才能列入supported_urls；仅出现产品名、企业名或相邻概念不算支持。
2. 目标含多个重要事实时，supported_urls合计必须覆盖全部重要事实才能标记supported；只覆盖部分标记partial；均不支持标记unsupported。
3. 分析判断允许由事实来源支撑，但必须保留条件和限制，不能把企业宣传升级为独立事实。
4. API、MCP、插件、连接器、Skill分别审核，不能互相替代。
5. 只使用证据中实际出现的URL，不得补造。reason简要说明未覆盖的事实。

待审目标：
{json.dumps(targets, ensure_ascii=False, indent=2)}

任务卡片与实际公开证据：
以下内容只保留目标实际引用的证据，未被引用的搜索结果已排除，以避免错配。
{json.dumps({"public_evidence": evidence_payload, "identity_sources": candidate_identity_sources}, ensure_ascii=False, indent=2)}

输出JSON必须符合：
{schema}
"""
        audit = generate_validated_json(
            self.model,
            "你是报告证据相关性审计器，只核对来源与主张的直接支持关系，严格输出JSON。",
            prompt,
            CitationAuditResult,
            contract_name="模型返回内容不符合P2.3.4证据相关性审计契约",
        )
        expected = {str(item["target_id"]) for item in targets}
        by_target = {item.target_id: item for item in audit.items if item.target_id in expected}
        allowed_urls = {
            _normalize_url(item.url) for item in documents
        } | {
            _normalize_url(item.url) for item in task.sources
        }
        failures: list[str] = []
        for target_id in sorted(expected):
            item = by_target.get(target_id)
            if item is None or item.status != "supported":
                failures.append(target_id)
                continue
            item.supported_urls = [
                url for url in item.supported_urls if _normalize_url(url) in allowed_urls
            ]
            if not item.supported_urls:
                failures.append(target_id)
        return audit, failures

    @staticmethod
    def _prune_failed_targets(
        draft: ReportDraft,
        audit: CitationAuditResult,
        failures: list[str],
        task: Task | None = None,
    ) -> ReportDraft:
        """Fail closed by removing unsupported prose instead of forcing template fill."""
        failed = set(failures)
        by_target = {item.target_id: item for item in audit.items}

        summaries: list[str] = []
        summary_urls: list[list[str]] = []
        for index, summary in enumerate(draft.executive_summary, start=1):
            target_id = f"summary:{index}"
            item = by_target.get(target_id)
            if target_id not in failed and item and item.supported_urls:
                summaries.append(summary)
                summary_urls.append(item.supported_urls)
        identity_urls: list[str] = []
        identity_claims: set[str] = set()
        if task is not None:
            required_claims = {"identity", "operator", "legal_ai_scope"}
            for source in task.sources:
                matched_claims = required_claims.intersection(source.supports)
                if matched_claims:
                    identity_claims.update(matched_claims)
                    if source.url not in identity_urls:
                        identity_urls.append(source.url)
        identity_fallback_available = bool(
            task
            and task.canonical_product_name
            and task.operator_name
            and {"identity", "operator", "legal_ai_scope"}.issubset(identity_claims)
            and identity_urls
        )
        if not summaries:
            if not identity_fallback_available or task is None:
                raise ProviderInvalidResponse(
                    "证据相关性复核后没有任何可保留的摘要，已停止生成Word"
                )
            summaries = [
                f"公开来源可确认{task.canonical_product_name}由{task.operator_name}运营，"
                "并用于法律AI相关场景；其余分析仅在本次公开证据可直接支持的范围内保留。"
            ]
            summary_urls = [identity_urls]
        draft.executive_summary = summaries
        draft.executive_summary_item_source_urls = summary_urls
        draft.executive_summary_source_urls = list(
            dict.fromkeys(url for urls in summary_urls for url in urls)
        )

        for index, section in enumerate(draft.sections, start=1):
            if f"section:{index}" in failed:
                section.paragraphs = ["当前公开证据不足以形成可靠结论。"]
                section.key_points = ["本维度暂不作强判断。"]
                section.source_urls = []

        insights: list[ReportInsightDraft] = []
        for index, insight in enumerate(draft.insights, start=1):
            target_id = f"insight:{index}"
            item = by_target.get(target_id)
            if target_id not in failed and item and item.supported_urls:
                insight.source_urls = item.supported_urls
                insights.append(insight)
        if not insights:
            if not identity_fallback_available:
                raise ProviderInvalidResponse(
                    "证据相关性复核后没有任何可保留的洞察，已停止生成Word"
                )
            insights = [
                ReportInsightDraft(
                    title="公开证据边界较窄",
                    analysis=(
                        "当前公开资料足以支持产品身份与法律AI用途，但不足以据此判断"
                        "经营质量、市场地位或商业化成效。"
                    ),
                    source_urls=identity_urls,
                )
            ]
        draft.insights = insights
        limitation = "部分摘要、章节或洞察因公开来源不能直接支持具体主张，已从测试稿中缩减或删除。"
        if limitation not in draft.limitations:
            draft.limitations.append(limitation)
        return draft

    @staticmethod
    def _apply_audit_urls(draft: ReportDraft, audit: CitationAuditResult) -> None:
        by_target = {item.target_id: item for item in audit.items if item.status == "supported"}
        summary_urls: list[str] = []
        summary_item_urls: list[list[str]] = []
        for index in range(1, len(draft.executive_summary) + 1):
            item = by_target.get(f"summary:{index}")
            item_urls = item.supported_urls if item else []
            summary_item_urls.append(item_urls)
            if item:
                for url in item.supported_urls:
                    if url not in summary_urls:
                        summary_urls.append(url)
        draft.executive_summary_source_urls = summary_urls
        draft.executive_summary_item_source_urls = summary_item_urls
        for index, section in enumerate(draft.sections, start=1):
            item = by_target.get(f"section:{index}")
            if item:
                section.source_urls = item.supported_urls
        for index, insight in enumerate(draft.insights, start=1):
            item = by_target.get(f"insight:{index}")
            if item:
                insight.source_urls = item.supported_urls

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
        prompt = f"""请为已通过身份闸门的法律AI产品制作P2.3.4本地Word测试稿。

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
            contract_name="模型返回内容不符合P2.3.4报告草稿契约",
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
                contract_name="模型未完成P2.3.4主张—证据绑定修复",
            )
            remaining_gaps = _citation_gaps(draft, allowed_urls)
            if remaining_gaps:
                raise ProviderInvalidResponse(
                    "模型未完成主张—证据绑定（"
                    + "、".join(remaining_gaps)
                    + "），已停止生成Word"
                )
        audit, audit_failures = self._audit_citations(draft, documents, task)
        if audit_failures:
            audit_details = {
                item.target_id: {"status": item.status, "reason": item.reason}
                for item in audit.items
                if item.target_id in audit_failures
            }
            relevance_repair_prompt = f"""证据相关性修复任务：上一版存在候选来源不能直接支持正文主张的问题。

不通过目标：{json.dumps(audit_details, ensure_ascii=False, indent=2)}

请重写这些目标，删除无证据事实或改为证据能够直接支持的有限表述，并重新填写真正支持该目标全部重要事实的source_urls。不得只替换URL而保留无证据主张；不得增加证据外的事实。其他部分保持紧凑。sources输出空数组。

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
                relevance_repair_prompt,
                ReportDraft,
                contract_name="模型未完成P2.3.4证据相关性修复",
            )
            audit, audit_failures = self._audit_citations(draft, documents, task)
            if audit_failures:
                draft = self._prune_failed_targets(draft, audit, audit_failures, task)
            else:
                self._apply_audit_urls(draft, audit)
        product = task.canonical_product_name or task.submitted_product_name
        draft.report_title = f"{product}标杆分析报告"
        draft.report_subtitle = "法律科技赛道 · P2.3.4证据相关性与冲突处理测试稿"
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
        for identity_limitation in task.limitations:
            inherited_limitation = f"身份核验阶段：{identity_limitation}"
            if inherited_limitation not in draft.limitations:
                draft.limitations.append(inherited_limitation)
        timeline_note = _timeline_conflict_note(documents)
        if timeline_note and timeline_note not in draft.limitations:
            draft.limitations.append(timeline_note)
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
            report_subtitle="法律科技赛道 · P2.3.4虚构测试稿",
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
        draft.executive_summary_item_source_urls = [[source_url]]
        return draft


class UnavailableReportDraftProvider:
    ready = False

    def generate(self, task: Task) -> ReportDraft:
        raise ProviderNotConfigured("当前身份适配器尚未实现P2.3.4报告生成")


def report_provider_from_identity(identity_provider) -> ReportDraftProvider:
    if isinstance(identity_provider, ExternalSearchIdentityProvider):
        return EvidenceBoundReportDraftProvider(identity_provider.model, identity_provider.search)
    if isinstance(identity_provider, FixtureIdentityResearchProvider):
        return FixtureReportDraftProvider()
    return UnavailableReportDraftProvider()
