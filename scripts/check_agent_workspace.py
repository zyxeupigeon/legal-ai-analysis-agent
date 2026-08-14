"""Cross-platform workspace preflight that does not depend on PowerShell script execution."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROTOCOL_ID = "portable-agent-0.7"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def available_word_com() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
            return True
    except OSError:
        return False


def find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        for candidate in (
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
    return None


def find_pdf_renderer() -> str | None:
    command = shutil.which("pdftoppm")
    if command:
        return command
    for module_name in ("pymupdf", "fitz"):
        if importlib.util.find_spec(module_name) is not None:
            return f"Python module: {module_name}"
    return None


def main() -> int:
    checks: list[tuple[str, bool, bool, str]] = []
    current_root = Path.cwd().resolve()
    checks.append(("project_root", True, current_root == PROJECT_ROOT, f"current={current_root}; expected={PROJECT_ROOT}"))

    declared_root = os.environ.get("LEGAL_AI_PROJECT_ROOT")
    binding_ok = not declared_root or Path(declared_root).resolve() == PROJECT_ROOT
    binding_detail = (
        f"launcher={Path(declared_root).resolve()}; expected={PROJECT_ROOT}"
        if declared_root
        else "launcher binding not set; current directory is authoritative"
    )
    checks.append(("launcher_root_binding", True, binding_ok, binding_detail))

    required_files = (
        "PROJECT_AGENT_PROTOCOL.md",
        "agent/core/v1.1/SYSTEM_PROMPT.md",
        "agent/core/v1.1/WORKFLOW.md",
        "agent/skills/legal-report-review-and-verification/SKILL.md",
        "scripts/create_task_workspace.py",
    )
    for relative in required_files:
        path = PROJECT_ROOT / relative
        checks.append((f"file:{relative}", True, path.is_file(), str(path)))

    checks.append(("python", True, True, sys.executable))

    output_root = PROJECT_ROOT / "agent_outputs"
    write_ok = False
    detail = str(output_root)
    try:
        output_root.mkdir(exist_ok=True)
        handle, probe = tempfile.mkstemp(prefix=".write_probe_", dir=output_root)
        os.close(handle)
        Path(probe).unlink()
        write_ok = True
    except OSError as exc:
        detail = f"{output_root}: {exc}"
    checks.append(("output_writable", True, write_ok, detail))

    office = "Microsoft Word COM" if available_word_com() else find_libreoffice()
    checks.append(("docx_to_pdf", False, bool(office), office or "not found; install Microsoft Word or LibreOffice"))
    renderer = find_pdf_renderer()
    checks.append(("pdf_to_png", False, bool(renderer), renderer or "not found; install Poppler or PyMuPDF"))
    self_test = PROJECT_ROOT / "scripts" / "self_test_document_pipeline.py"
    checks.append(("self_test_script", True, self_test.is_file(), str(self_test)))

    print(f"{'CHECK':<48} {'REQUIRED':<8} {'PASSED':<7} DETAIL")
    for name, required, passed, check_detail in checks:
        print(f"{name:<48} {str(required):<8} {str(passed):<7} {check_detail}")

    failed = [item for item in checks if item[1] and not item[2]]
    if failed:
        print(f"Portable Agent preflight failed: {len(failed)} required check(s) failed.", file=sys.stderr)
        return 1

    local_pipeline_ready = all(
        item[2] for item in checks if item[0] in {"docx_to_pdf", "pdf_to_png"}
    )
    print(f"PREFLIGHT_BASE_OK protocol={PROTOCOL_ID}")
    print("SESSION_GATE_REQUIRED declare READY only if the current conversation can continue normally without user decisions or restart")
    print(f"LOCAL_DOCUMENT_PIPELINE_READY {str(local_pipeline_ready).lower()}")
    print("TIP run START_AGENT.cmd -SelfTest before the first real analysis")
    print("NOTE internet search, page reading, model access, and visual document inspection must be declared by the running Agent; this local script cannot prove them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())