"""Allocate a task output directory anchored to this project copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from execution_trace_lib import atomic_write_json, new_trace
from session_preflight_gate import consume_capability_receipt, validate_capability_receipt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "agent_outputs"
PROTOCOL_ID = "portable-agent-1.0"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
PROTECTED_FIXED_PATHS = (
    "PROJECT_AGENT_PROTOCOL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "agent/core/v1.1/WORKFLOW.md",
    "agent/skills/legal-report-review-and-verification/SKILL.md",
    "scripts/check_agent_workspace.py",
    "scripts/session_preflight_gate.py",
    "scripts/start_agent.py",
    "scripts/create_task_workspace.py",
    "scripts/execution_trace_lib.py",
    "scripts/record_execution_event.py",
    "scripts/build_process_optimization_report.py",
    "scripts/report_version_lib.py",
    "scripts/compare_report_versions.py",
    "scripts/build_report_manifest.py",
    "scripts/render_report.py",
    "scripts/self_test_document_pipeline.py",
    "scripts/create_self_test_docx.py",
    "docs/EXECUTION_TRACE_SCHEMA.md",
    "docs/PROCESS_OPTIMIZATION_REPORT_TEMPLATE.md",
    "docs/REPORT_VERSIONING.md",
    "scripts/validate_portable_agent_output.py",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_project_hashes() -> dict[str, str]:
    relative_paths = list(PROTECTED_FIXED_PATHS)
    evaluation_root = PROJECT_ROOT / "evaluations"
    if evaluation_root.is_dir():
        relative_paths.extend(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in sorted(evaluation_root.glob("*.json"))
        )
    hashes = {}
    for relative_path in relative_paths:
        path = PROJECT_ROOT / relative_path
        if not path.is_file():
            raise RuntimeError(f"protected project file is missing: {relative_path}")
        hashes[relative_path] = file_sha256(path)
    return hashes


def verify_project_binding() -> None:
    current_root = Path.cwd().resolve()
    if current_root != PROJECT_ROOT:
        raise RuntimeError(
            f"current working directory is {current_root}; expected project root {PROJECT_ROOT}"
        )

    declared_root = os.environ.get("LEGAL_AI_PROJECT_ROOT")
    if declared_root and Path(declared_root).resolve() != PROJECT_ROOT:
        raise RuntimeError(
            f"launcher project root is {Path(declared_root).resolve()}; script project root is {PROJECT_ROOT}"
        )


def allocate(task_id: str, session_gate: str, capability_receipt: Path) -> Path:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("task id must use 1-80 ASCII letters, digits, underscores, or hyphens")
    if session_gate != "READY":
        raise RuntimeError(
            "session preflight is not READY; do not create a task workspace or generate a report"
        )
    verify_project_binding()
    receipt = validate_capability_receipt(capability_receipt, PROJECT_ROOT)
    project_hashes = protected_project_hashes()
    output_dir = (OUTPUT_ROOT / task_id).resolve()
    if not output_dir.is_relative_to(OUTPUT_ROOT.resolve()):
        raise RuntimeError("task output path escaped agent_outputs")
    output_dir.mkdir(parents=True, exist_ok=False)
    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    context = {
        "protocol_id": PROTOCOL_ID,
        "project_root": str(PROJECT_ROOT),
        "output_root": str(OUTPUT_ROOT.resolve()),
        "task_output_dir": str(output_dir),
        "created_at": created_at,
        "session_gate": session_gate,
        "session_capability_receipt_id": receipt["receipt_id"],
        "session_capabilities": receipt["capabilities"],
        "visual_probe_verified": receipt["visual_probe_verified"],
        "document_self_test": receipt["document_self_test"],
        "protected_project_hashes": project_hashes,
    }
    (output_dir / "task_context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    atomic_write_json(output_dir / "execution_trace.json", new_trace(task_id, created_at))
    consume_capability_receipt(capability_receipt, task_id, PROJECT_ROOT)
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--session-gate", required=True, choices=("READY", "BLOCKED"))
    parser.add_argument("--capability-receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        output_dir = allocate(args.task_id, args.session_gate, args.capability_receipt)
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        print("TASK_WORKSPACE_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc
    print("TASK_WORKSPACE_OK")
    print(f"PROJECT_ROOT={PROJECT_ROOT}")
    print(f"TASK_OUTPUT_DIR={output_dir}")


if __name__ == "__main__":
    main()
