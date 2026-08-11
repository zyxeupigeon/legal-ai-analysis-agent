import subprocess
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_standard_library_self_test_docx_is_valid(tmp_path: Path) -> None:
    output_path = tmp_path / "self-test.docx"
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "create_self_test_docx.py"), str(output_path)],
        check=True,
    )

    assert output_path.is_file()
    with zipfile.ZipFile(output_path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/document.xml",
        }
        document = archive.read("word/document.xml").decode("utf-8")
    assert "SELF_TEST_DOCUMENT_PIPELINE_OK" in document


def test_windows_launcher_exposes_self_test_without_installing_dependencies() -> None:
    launcher = (REPO_ROOT / "scripts" / "start_agent.ps1").read_text(encoding="utf-8")
    self_test = (REPO_ROOT / "scripts" / "self_test_document_pipeline.ps1").read_text(encoding="utf-8")

    assert "[switch]$SelfTest" in launcher
    assert "self_test_document_pipeline.ps1" in launcher
    assert "SELF_TEST_OK" in self_test
    assert "SELF_TEST_FAIL" in self_test
    assert "pip install" not in self_test
    assert "Remove-Item -LiteralPath $resolvedTestDirectory -Recurse -Force" in self_test
