import json

import pytest
from docx import Document

from services.api.app.models import (
    IdentityGate,
    ReportDraft,
    ReportInsightDraft,
    ReportSectionDraft,
    ReportSourceRecord,
    Task,
    TaskStatus,
)
from services.api.app.provider_errors import ProviderInvalidResponse
from services.api.app.report_document import build_report_docx
from services.api.app.report_provider import (
    REPORT_SECTION_HEADINGS,
    EvidenceBoundReportDraftProvider,
    FixtureReportDraftProvider,
)
from services.api.app.search_provider import SearchDocument


class FakeModel:
    ready = True
    model_name = "fixture-report-model"
    provider_name = "fixture"

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        assert "不得使用模型记忆" in system_prompt
        assert "actual.example/product" in user_prompt
        return json.dumps(self.payload, ensure_ascii=False)


class SequenceModel(FakeModel):
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append(user_prompt)
        return json.dumps(self.payloads.pop(0), ensure_ascii=False)


class FakeSearch:
    ready = True
    provider_name = "fixture-search"
    search_tier = "test_only"

    def search(self, query: str, *, max_results: int = 5) -> list[SearchDocument]:
        return [
            SearchDocument(
                query=query,
                title="产品官方说明",
                url="https://actual.example/product",
                content="该文本仅用于测试证据约束。",
                retrieval_status="readable",
            )
        ]


def fixture_task() -> Task:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return Task(
        task_id="fixture-task",
        submitted_product_name="衡法智研",
        canonical_product_name="衡法智研",
        operator_name="衡法科技",
        product_type="法律AI研究产品",
        task_status=TaskStatus.RESEARCHING,
        identity_gate=IdentityGate.CONFIRMED,
        status_message="测试",
        created_at=now,
        updated_at=now,
    )


def report_payload(source_urls: list[str]) -> dict:
    return {
        "report_title": "会被系统覆盖",
        "report_subtitle": "会被系统覆盖",
        "executive_summary": ["测试摘要。"],
        "sections": [
            {
                "heading": f"模型自拟标题{index}",
                "paragraphs": ["只描述测试证据。"],
                "key_points": ["测试要点。"],
                "source_urls": source_urls,
            }
            for index in range(5)
        ],
        "insights": [
            {
                "title": "测试洞察",
                "analysis": "只验证引用过滤。",
                "source_urls": source_urls,
            }
        ],
        "limitations": [],
        "sources": [],
    }


def test_report_provider_keeps_only_retrieved_sources_and_fixed_headings() -> None:
    provider = EvidenceBoundReportDraftProvider(
        FakeModel(report_payload(["https://actual.example/product", "https://invented.example"])),
        FakeSearch(),
    )
    draft = provider.generate(fixture_task())

    assert [section.heading for section in draft.sections] == REPORT_SECTION_HEADINGS
    assert draft.sections[0].source_urls == ["https://actual.example/product"]
    assert [source.url for source in draft.sources] == ["https://actual.example/product"]
    assert any("免费测试级公开检索" in item for item in draft.limitations)


def test_report_provider_rejects_draft_without_real_citation() -> None:
    provider = EvidenceBoundReportDraftProvider(
        FakeModel(report_payload(["https://invented.example"])),
        FakeSearch(),
    )
    with pytest.raises(ProviderInvalidResponse, match="没有引用任何实际检索来源"):
        provider.generate(fixture_task())


def test_report_provider_repairs_invalid_contract_once() -> None:
    model = SequenceModel(
        [
            {"report_title": "缺少字段"},
            report_payload(["https://actual.example/product"]),
        ]
    )
    provider = EvidenceBoundReportDraftProvider(model, FakeSearch())

    draft = provider.generate(fixture_task())

    assert len(draft.sections) == 5
    assert len(model.prompts) == 2
    assert "格式修复任务" in model.prompts[1]


def test_report_provider_normalizes_short_section_list_without_inventing_facts() -> None:
    payload = report_payload(["https://actual.example/product"])
    payload["sections"] = payload["sections"][:3]
    payload["sources"] = [{"unexpected": "model ledger is ignored"}]
    provider = EvidenceBoundReportDraftProvider(FakeModel(payload), FakeSearch())

    draft = provider.generate(fixture_task())

    assert len(draft.sections) == 5
    assert draft.sections[3].paragraphs == ["当前公开证据不足以形成可靠结论。"]
    assert [source.url for source in draft.sources] == ["https://actual.example/product"]


def test_word_builder_creates_editable_document(tmp_path) -> None:
    task = fixture_task()
    draft = FixtureReportDraftProvider().generate(task)
    output = tmp_path / "fixture.docx"

    build_report_docx(draft, task, output)
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert output.read_bytes().startswith(b"PK")
    assert "衡法智研标杆分析报告" in text
    assert all(heading in text for heading in REPORT_SECTION_HEADINGS)
    assert "主要数据来源一览" in text
