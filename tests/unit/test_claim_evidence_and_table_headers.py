import importlib.util
import json
import zipfile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate_portable_agent_output.py"
SPEC = importlib.util.spec_from_file_location("validate_portable_agent_output", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_docx(path: Path, second_table_repeats: bool) -> None:
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    repeat = "<w:trPr><w:tblHeader/></w:trPr>" if second_table_repeats else ""
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{namespace}"><w:body>
<w:tbl><w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:p/></w:tc></w:tr></w:tbl>
<w:tbl><w:tr>{repeat}<w:tc><w:p/></w:tc></w:tr></w:tbl>
</w:body></w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def test_table_header_guard_detects_non_repeating_table(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    write_docx(report, second_table_repeats=False)
    assert MODULE.tables_without_repeating_headers(report) == [2]


def test_table_header_guard_accepts_repeating_headers(tmp_path: Path) -> None:
    report = tmp_path / "report.docx"
    write_docx(report, second_table_repeats=True)
    assert MODULE.tables_without_repeating_headers(report) == []


def test_claim_evidence_accepts_primary_dynamic_fact_and_analysis(tmp_path: Path) -> None:
    source_url = "https://example.com/official-price"
    payload = {
        "schema_version": "1.0",
        "claims": [
            {
                "claim_id": "C001",
                "claim_text": "官方价格为4元/页",
                "claim_type": "verified_fact",
                "category": "pricing",
                "source_url": source_url,
                "source_tier": "A",
                "accessed_at": "2026-08-14",
                "report_location": "经营/定价",
                "included_in_report": True,
            },
            {
                "claim_id": "A001",
                "claim_text": "按量计费降低试用门槛",
                "claim_type": "analysis",
                "category": "commercial_analysis",
                "based_on_claim_ids": ["C001"],
                "report_location": "洞察",
                "included_in_report": True,
            },
        ],
    }
    path = tmp_path / "claim_evidence.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    errors = []
    assert MODULE.validate_claim_evidence(path, [source_url], errors) == 2
    assert errors == []


def test_claim_evidence_rejects_weak_current_model_version(tmp_path: Path) -> None:
    source_url = "https://example.com/third-party"
    payload = {
        "schema_version": "1.0",
        "claims": [
            {
                "claim_id": "C001",
                "claim_text": "当前模型为未经官方证实的新版本",
                "claim_type": "company_claim",
                "category": "current_model_version",
                "source_url": source_url,
                "source_tier": "B",
                "accessed_at": "2026-08-14",
                "report_location": "洞察",
                "included_in_report": True,
            }
        ],
    }
    path = tmp_path / "claim_evidence.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    errors = []
    MODULE.validate_claim_evidence(path, [source_url], errors)
    assert any("requires a primary official source" in error for error in errors)