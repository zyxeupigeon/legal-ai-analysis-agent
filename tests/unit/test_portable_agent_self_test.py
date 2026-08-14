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


def test_windows_launcher_avoids_downloaded_powershell_scripts() -> None:
    command_launcher = (REPO_ROOT / "START_AGENT.cmd").read_text(encoding="ascii")
    launcher = (REPO_ROOT / "scripts" / "start_agent.py").read_text(encoding="utf-8")
    self_test = (REPO_ROOT / "scripts" / "self_test_document_pipeline.py").read_text(encoding="utf-8")

    assert "scripts\\start_agent.py" in command_launcher
    assert "powershell.exe" not in command_launcher.lower()
    assert '"-SelfTest"' in launcher
    assert "SELF_TEST_OK" in self_test
    assert "SELF_TEST_FAIL" in self_test
    assert "pip install" not in self_test
    assert "shutil.rmtree(directory, ignore_errors=True)" in self_test