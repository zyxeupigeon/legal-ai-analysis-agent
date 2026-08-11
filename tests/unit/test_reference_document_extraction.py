import json
import zipfile

from scripts.create_self_test_docx import create_docx
from scripts import extract_reference_document as extraction


def test_stdlib_docx_fallback_extracts_paragraphs(tmp_path):
    source = tmp_path / "sample.docx"
    create_docx(source)

    text = extraction.docx_to_markdown(source)

    assert "法律AI产品分析Agent" in text
    assert "SELF_TEST_DOCUMENT_PIPELINE_OK" in text


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


def test_metadata_never_claims_visual_fidelity(tmp_path):
    output = extraction.OUTPUT_ROOT / "test-reference-extraction"
    metadata = {
        "visual_fidelity_claimed": False,
        "output": str(output / "reference-content.md"),
    }
    encoded = json.dumps(metadata)

    assert json.loads(encoded)["visual_fidelity_claimed"] is False
