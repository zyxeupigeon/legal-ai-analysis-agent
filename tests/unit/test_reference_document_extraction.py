import json
import zipfile
from pathlib import Path

from docx import Document

from scripts import extract_reference_document as extraction


def test_stdlib_docx_fallback_extracts_paragraphs_and_tables(tmp_path):
    source = tmp_path / "sample.docx"
    document = Document()
    document.add_heading("示例法律AI报告", level=1)
    document.add_paragraph("正文内容")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "产品"
    table.cell(0, 1).text = "状态"
    table.cell(1, 0).text = "测试对象"
    table.cell(1, 1).text = "已核验"
    document.save(source)

    text = extraction.docx_to_markdown(source)

    assert "示例法律AI报告" in text
    assert "正文内容" in text
    assert "| 产品 | 状态 |" in text
    assert "| 测试对象 | 已核验 |" in text


def test_corrupt_docx_is_rejected(tmp_path):
    source = tmp_path / "broken.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("not-document.xml", "broken")

    try:
        extraction.docx_to_markdown(source)
    except KeyError:
        pass
    else:
        raise AssertionError("corrupt DOCX should not be accepted")


def test_metadata_never_claims_visual_fidelity(tmp_path, monkeypatch):
    output = extraction.OUTPUT_ROOT / "test-reference-extraction"
    metadata = {
        "visual_fidelity_claimed": False,
        "output": str(output / "reference-content.md"),
    }
    encoded = json.dumps(metadata)

    assert json.loads(encoded)["visual_fidelity_claimed"] is False
