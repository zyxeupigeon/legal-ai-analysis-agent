"""Exercise DOCX -> PDF -> PNG without executing downloaded PowerShell script files."""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def word_to_pdf(docx: Path, pdf: Path) -> bool:
    if os.name == "nt":
        env = os.environ.copy()
        env["LEGAL_AI_SELF_TEST_DOCX"] = str(docx)
        env["LEGAL_AI_SELF_TEST_PDF"] = str(pdf)
        script = (
            "$ErrorActionPreference='Stop';"
            "$word=New-Object -ComObject Word.Application;"
            "$word.Visible=$false;"
            "try{$doc=$word.Documents.Open($env:LEGAL_AI_SELF_TEST_DOCX);"
            "try{$doc.SaveAs2($env:LEGAL_AI_SELF_TEST_PDF,17)}finally{$doc.Close($false)}}"
            "finally{$word.Quit()}"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and pdf.is_file() and pdf.stat().st_size:
            return True

    office = shutil.which("soffice") or shutil.which("libreoffice")
    if office:
        result = subprocess.run(
            [office, "--headless", "--convert-to", "pdf", "--outdir", str(pdf.parent), str(docx)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and pdf.is_file() and pdf.stat().st_size > 0
    return False


def pdf_to_png(pdf: Path, output: Path) -> bool:
    for module_name in ("pymupdf", "fitz"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        document = module.open(pdf)
        try:
            if len(document) < 1:
                return False
            pixmap = document[0].get_pixmap(matrix=module.Matrix(1.5, 1.5), alpha=False)
            pixmap.save(output)
            return output.is_file() and output.stat().st_size > 0
        finally:
            document.close()

    renderer = shutil.which("pdftoppm")
    if renderer:
        prefix = output.with_suffix("")
        result = subprocess.run(
            [renderer, "-f", "1", "-singlefile", "-png", str(pdf), str(prefix)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and output.is_file() and output.stat().st_size > 0
    return False


def main() -> int:
    output_root = PROJECT_ROOT / "agent_outputs"
    output_root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=".self_test_", dir=output_root))
    try:
        docx = directory / "self-test.docx"
        pdf = directory / "self-test.pdf"
        png = directory / "self-test.png"
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "create_self_test_docx.py"), str(docx)],
            check=True,
        )
        if not word_to_pdf(docx, pdf):
            print("SELF_TEST_FAIL - DOCX to PDF conversion unavailable", file=sys.stderr)
            return 1
        if not pdf_to_png(pdf, png):
            print("SELF_TEST_FAIL - PDF to PNG rendering unavailable", file=sys.stderr)
            return 1
        print(f"SELF_TEST_OK docx={docx.name} pdf={pdf.name} png={png.name}")
        return 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"SELF_TEST_FAIL - {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())