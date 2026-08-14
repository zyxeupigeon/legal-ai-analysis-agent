from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPERS_PATH = Path(__file__).with_name("test_report_versioning.py")
SPEC = importlib.util.spec_from_file_location("complete_output_test_helpers", HELPERS_PATH)
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


def run_script(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_minimal_docx(path: Path) -> None:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>测试法律AI产品分析报告</w:t></w:r></w:p></w:body>'
        '</w:document>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)


def write_capability_receipt() -> Path:
    receipt_dir = REPO_ROOT / "tmp" / "session_preflight" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_id = uuid.uuid4().hex
    path = receipt_dir / f"{receipt_id}.json"
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "protocol_id": "portable-agent-1.0",
        "receipt_id": receipt_id,
        "challenge_id": "unit-test",
        "project_root": str(REPO_ROOT.resolve()),
        "created_at": "2026-08-14T00:00:00.000+00:00",
        "expires_at": "2099-08-14T00:00:00.000+00:00",
        "used_at": None,
        "used_for_task_id": None,
        "visual_probe_verified": True,
        "document_self_test": "READY",
        "capabilities": {
            "internet_search": "READY",
            "page_reading": "READY",
            "word_generation": "READY",
            "pdf_png_rendering": "READY",
            "direct_image_inspection": "READY",
        },
    }, indent=2), encoding="utf-8")
    return path


def test_complete_cli_output_passes_then_tampering_is_rejected() -> None:
    unique = uuid.uuid4().hex[:12]
    task_id = f"contract_{unique}"
    task_dir = REPO_ROOT / "agent_outputs" / task_id
    subject = f"完整验收测试产品-{unique}"
    source_url = f"https://official.example/{unique}/pricing"
    receipt_path = write_capability_receipt()
    try:
        result = run_script(
            "scripts/create_task_workspace.py",
            "--task-id",
            task_id,
            "--session-gate",
            "READY",
            "--capability-receipt",
            str(receipt_path),
        )
        assert result.returncode == 0, result.stdout + result.stderr

        (task_dir / "execution_trace.json").write_text(
            json.dumps(HELPERS.complete_trace(task_id), ensure_ascii=False), encoding="utf-8"
        )
        write_minimal_docx(task_dir / "report.docx")
        (task_dir / "sources.md").write_text(f"- {source_url}\n", encoding="utf-8")
        claims = {
            "schema_version": "1.0",
            "task_id": task_id,
            "claims": [{
                "claim_id": "C001",
                "claim_text": "官方价格为4元每页",
                "claim_type": "verified_fact",
                "category": "pricing",
                "source_url": source_url,
                "source_tier": "A",
                "accessed_at": "2026-08-14",
                "report_location": "定价",
                "included_in_report": True,
            }],
        }
        (task_dir / "claim_evidence.json").write_text(
            json.dumps(claims, ensure_ascii=False), encoding="utf-8"
        )
        (task_dir / "capability_declaration.md").write_text(
            "已声明公开检索、Word生成、渲染和视觉检查能力。\n", encoding="utf-8"
        )
        render = task_dir / "render"
        render.mkdir()
        (render / "report.pdf").write_bytes(b"synthetic-pdf")
        (render / "page-1.png").write_bytes(b"synthetic-png")

        result = run_script(
            "scripts/build_process_optimization_report.py",
            str(task_dir),
            "--subject",
            subject,
            "--agent",
            "Test Agent",
            "--model",
            "Test Model",
            "--status",
            "PASS",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        result = run_script(
            "scripts/compare_report_versions.py", str(task_dir), "--subject", subject
        )
        assert result.returncode == 0, result.stdout + result.stderr
        result = run_script(
            "scripts/build_report_manifest.py",
            str(task_dir),
            "--subject",
            subject,
            "--status",
            "PASS",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        (task_dir / "run_summary.md").write_text(
            "# 运行摘要\n\n总体状态：PASS\n", encoding="utf-8"
        )

        result = run_script("scripts/validate_portable_agent_output.py", str(task_dir))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PORTABLE_AGENT_OUTPUT_OK" in result.stdout

        (task_dir / "sources.md").write_text("tampered\n", encoding="utf-8")
        result = run_script("scripts/validate_portable_agent_output.py", str(task_dir))
        assert result.returncode == 1
        assert "manifest artifact hash mismatch: sources.md" in result.stdout
    finally:
        if task_dir.is_dir() and task_dir.resolve().parent == (REPO_ROOT / "agent_outputs").resolve():
            shutil.rmtree(task_dir)
        if receipt_path.is_file():
            receipt_path.unlink()
