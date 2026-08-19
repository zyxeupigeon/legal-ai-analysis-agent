from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from execution_trace_lib import REQUIRED_REPORT_STAGES, new_trace, validate_trace
from report_version_lib import extract_urls_from_text, subject_key, validate_manifest


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DIFF = load_module("compare_report_versions", "compare_report_versions.py")
MANIFEST = load_module("build_report_manifest", "build_report_manifest.py")


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds")


def complete_trace(task_id: str, duration_multiplier: int = 1) -> dict:
    start = datetime(2026, 8, 14, tzinfo=timezone.utc)
    payload = new_trace(task_id, iso(start))
    cursor = start + timedelta(seconds=1)
    for stage in sorted(REQUIRED_REPORT_STAGES - {"workspace_allocation"}):
        end = cursor + timedelta(seconds=duration_multiplier)
        sequence = len(payload["events"]) + 1
        payload["events"].append({
            "event_id": f"E{sequence:04d}",
            "sequence": sequence,
            "stage": stage,
            "action": f"Complete {stage}",
            "tool": "test-tool",
            "started_at": iso(cursor),
            "ended_at": iso(end),
            "duration_seconds": float(duration_multiplier),
            "status": "succeeded",
            "retry_of": None,
            "note": None,
            "artifacts": [],
        })
        cursor = end + timedelta(seconds=1)
    payload["observations"] = [{
        "observation_id": "O0001",
        "sequence": 1,
        "timestamp": iso(cursor),
        "stage": "visual_qa",
        "kind": "optimization_recommendation",
        "summary": "Reuse verified structured ledgers",
        "impact": "Reduce repeated comparison work",
        "resolution": None,
        "priority": "P1",
        "expected_benefit": "Faster report updates",
        "implementation_cost": "Low",
        "risk": "A stale baseline could be selected",
        "validation_method": "Verify manifest hashes before comparison",
    }]
    payload["updated_at"] = iso(cursor)
    payload["finalized_at"] = iso(cursor)
    assert validate_trace(
        payload, expected_task_id=task_id, require_finalized=True, require_report_stages=True
    ) == []
    return payload


def create_task(
    project_root: Path,
    task_id: str,
    *,
    price: str,
    source_url: str,
    duration_multiplier: int = 1,
) -> Path:
    output_root = project_root / "agent_outputs"
    task_dir = output_root / task_id
    (task_dir / "render").mkdir(parents=True)
    context = {
        "protocol_id": "portable-agent-1.1",
        "project_root": str(project_root.resolve()),
        "output_root": str(output_root.resolve()),
        "task_output_dir": str(task_dir.resolve()),
        "created_at": "2026-08-14T00:00:00.000+00:00",
        "session_gate": "READY",
        "session_capability_receipt_id": "synthetic-test-receipt",
        "visual_probe_verified": True,
        "document_self_test": "READY",
        "session_capabilities": {
            "internet_search": "READY",
            "page_reading": "READY",
            "word_generation": "READY",
            "pdf_png_rendering": "READY",
            "direct_image_inspection": "READY",
        },
        "protected_project_hashes": {"PROJECT_AGENT_PROTOCOL.md": "test"},
    }
    (task_dir / "task_context.json").write_text(
        json.dumps(context, ensure_ascii=False), encoding="utf-8"
    )
    (task_dir / "execution_trace.json").write_text(
        json.dumps(complete_trace(task_id, duration_multiplier), ensure_ascii=False), encoding="utf-8"
    )
    claims = {
        "schema_version": "1.0",
        "task_id": task_id,
        "claims": [
            {
                "claim_id": "C001",
                "claim_text": price,
                "claim_type": "verified_fact",
                "category": "pricing",
                "source_url": source_url,
                "source_tier": "A",
                "accessed_at": "2026-08-14",
                "report_location": "定价",
                "included_in_report": True,
            },
            {
                "claim_id": "A001",
                "claim_text": f"基于{price}形成商业判断",
                "claim_type": "analysis",
                "category": "commercial_analysis",
                "based_on_claim_ids": ["C001"],
                "report_location": "结论",
                "included_in_report": True,
            },
        ],
    }
    (task_dir / "claim_evidence.json").write_text(
        json.dumps(claims, ensure_ascii=False), encoding="utf-8"
    )
    (task_dir / "sources.md").write_text(f"- {source_url}\n", encoding="utf-8")
    for relative, content in {
        "report.docx": b"test-docx",
        "capability_declaration.md": b"capabilities",
        "process_optimization_report.md": b"optimization",
        "render/report.pdf": b"test-pdf",
        "render/page-1.png": b"test-png",
    }.items():
        (task_dir / relative).write_bytes(content)
    return task_dir


def test_first_run_creates_a_verified_manifest_and_no_baseline(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    task_dir = create_task(
        project_root,
        "product_20260814",
        price="官方价格为4元每页",
        source_url="https://official.example/pricing",
    )

    diff = DIFF.build_diff(task_dir, "测试法律AI", project_root)
    assert diff["baseline"]["status"] == "not_found"
    assert diff["claims"]["added"][0]["claim_id"] == "A001"
    assert "首次纳入版本管理" in (task_dir / "report_diff.md").read_text(encoding="utf-8")

    manifest = MANIFEST.build_manifest(task_dir, "测试法律AI", "PASS", project_root)
    assert manifest["subject_key"] == subject_key("测试法律AI")
    assert manifest["baseline_task_id"] is None
    assert validate_manifest(task_dir) == []


def test_second_run_selects_same_subject_and_compares_claims_sources_and_efficiency(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    first = create_task(
        project_root,
        "product_20260814",
        price="官方价格为4元每页",
        source_url="https://official.example/pricing-v1",
        duration_multiplier=1,
    )
    DIFF.build_diff(first, "测试法律AI", project_root)
    MANIFEST.build_manifest(first, "测试法律AI", "PASS", project_root)

    other = create_task(
        project_root,
        "other_20260815",
        price="另一个产品价格",
        source_url="https://other.example/pricing",
    )
    DIFF.build_diff(other, "另一个法律AI", project_root)
    MANIFEST.build_manifest(other, "另一个法律AI", "PASS", project_root)

    second = create_task(
        project_root,
        "product_20260816",
        price="官方价格为5元每页",
        source_url="https://official.example/pricing-v2",
        duration_multiplier=2,
    )
    diff = DIFF.build_diff(second, "测试法律AI", project_root)

    assert diff["baseline"]["task_id"] == first.name
    assert {item["claim_id"] for item in diff["claims"]["changed"]} == {"A001", "C001"}
    assert diff["dynamic_claims"]["changed"][0]["claim_id"] == "C001"
    assert diff["sources"] == {
        "added": ["https://official.example/pricing-v2"],
        "removed": ["https://official.example/pricing-v1"],
    }
    assert diff["efficiency"]["current"]["total_duration_seconds"] > diff["efficiency"]["baseline"]["total_duration_seconds"]
    assert any("一级官方来源" in reminder for reminder in diff["reminders"])


def test_manifest_detects_artifact_tampering(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    task_dir = create_task(
        project_root,
        "tamper_20260814",
        price="官方价格为4元每页",
        source_url="https://official.example/pricing",
    )
    DIFF.build_diff(task_dir, "测试法律AI", project_root)
    MANIFEST.build_manifest(task_dir, "测试法律AI", "PASS", project_root)

    mismatched = json.loads((task_dir / "report_manifest.json").read_text(encoding="utf-8"))
    mismatched["subject"] = "另一个产品"
    mismatched["subject_key"] = subject_key("另一个产品")
    assert "report manifest subject does not match report diff" in validate_manifest(task_dir, mismatched)

    (task_dir / "sources.md").write_text("tampered", encoding="utf-8")
    errors = validate_manifest(task_dir)
    assert "manifest artifact size mismatch: sources.md" in errors
    assert "manifest artifact hash mismatch: sources.md" in errors


def test_secret_like_subject_is_rejected(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    task_dir = create_task(
        project_root,
        "secret_20260814",
        price="官方价格为4元每页",
        source_url="https://official.example/pricing",
    )
    try:
        DIFF.build_diff(task_dir, "api_key=must-not-be-recorded", project_root)
    except ValueError as exc:
        assert "authentication material" in str(exc)
    else:
        raise AssertionError("secret-like subject was accepted")

def test_diff_rejects_blocked_context_and_mismatched_claim_task_id(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    task_dir = create_task(
        project_root,
        "binding_20260814",
        price="官方价格为4元每页",
        source_url="https://official.example/pricing",
    )
    context_path = task_dir / "task_context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["session_gate"] = "BLOCKED"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    try:
        DIFF.build_diff(task_dir, "测试法律AI", project_root)
    except ValueError as exc:
        assert "session gate must be READY" in str(exc)
    else:
        raise AssertionError("blocked task context was accepted")

    context["session_gate"] = "READY"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    claims_path = task_dir / "claim_evidence.json"
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    claims["task_id"] = "different_task"
    claims_path.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
    try:
        DIFF.build_diff(task_dir, "测试法律AI", project_root)
    except ValueError as exc:
        assert "task_id must match task directory" in str(exc)
    else:
        raise AssertionError("mismatched claim task id was accepted")

def test_url_extraction_stops_at_cjk_punctuation_and_brackets() -> None:
    text = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1\uFF09 "
        "https://tongyi.aliyun.com/farui/\uFF1B\u529F\u80FD\u5305\u62EC "
        "https://official.example/path?x=1&y=2."
    )
    assert extract_urls_from_text(text) == [
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://official.example/path?x=1&y=2",
        "https://tongyi.aliyun.com/farui/",
    ]


def test_manifest_rejects_unmanifested_formal_duplicates(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    task_dir = create_task(
        project_root,
        "duplicates_20260814",
        price="official price",
        source_url="https://official.example/pricing",
    )
    DIFF.build_diff(task_dir, "test legal AI", project_root)
    MANIFEST.build_manifest(task_dir, "test legal AI", "PASS", project_root)

    (task_dir / "alternate-name.docx").write_bytes(b"duplicate")
    (task_dir / "alternate-name.pdf").write_bytes(b"duplicate")
    errors = validate_manifest(task_dir)
    assert "unexpected unmanifested formal artifact: alternate-name.docx" in errors
    assert "unexpected unmanifested formal artifact: alternate-name.pdf" in errors
