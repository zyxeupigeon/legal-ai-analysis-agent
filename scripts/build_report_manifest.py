"""Build a tamper-evident manifest for a completed report task."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_version_lib import (
    FINAL_STATUSES,
    MANIFEST_SCHEMA_VERSION,
    atomic_write_json,
    file_sha256,
    load_json,
    safe_subject,
    subject_key,
    utc_now,
    validate_diff,
    validate_manifest,
    verify_task_directory,
)


ARTIFACT_ROLES = {
    "task_context.json": "task_context",
    "execution_trace.json": "execution_trace",
    "report.docx": "editable_report",
    "sources.md": "source_ledger",
    "claim_evidence.json": "claim_evidence_ledger",
    "capability_declaration.md": "capability_declaration",
    "process_optimization_report.md": "process_optimization_report",
    "report_diff.json": "machine_readable_version_diff",
    "report_diff.md": "human_readable_version_diff",
    "render/report.pdf": "rendered_report_pdf",
}


def artifact_paths(task_dir: Path) -> list[tuple[str, str]]:
    artifacts = list(ARTIFACT_ROLES.items())
    pages = sorted((task_dir / "render").glob("page-*.png"))
    artifacts.extend((path.relative_to(task_dir).as_posix(), "rendered_report_page") for path in pages)
    return artifacts


def build_manifest(task_dir: Path, subject: str, status: str, project_root: Path) -> dict:
    context = verify_task_directory(task_dir, project_root)
    task_dir = task_dir.resolve()
    subject = safe_subject(subject)
    status = status.upper()
    if status not in FINAL_STATUSES:
        raise ValueError("status must be PASS, PARTIAL, or FAIL")
    diff_errors = validate_diff(task_dir)
    if diff_errors:
        raise ValueError("report diff is invalid: " + "; ".join(diff_errors))
    diff = load_json(task_dir / "report_diff.json")
    if diff.get("subject_key") != subject_key(subject):
        raise ValueError("report diff subject does not match manifest subject")

    artifacts = []
    for relative, role in artifact_paths(task_dir):
        path = task_dir / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"required report artifact is missing or empty: {relative}")
        artifacts.append({
            "path": relative,
            "role": role,
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        })

    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "protocol_id": context["protocol_id"],
        "task_id": task_dir.name,
        "subject": subject,
        "subject_key": subject_key(subject),
        "completed_at": utc_now(),
        "final_status": status,
        "baseline_task_id": diff["baseline"].get("task_id"),
        "artifacts": artifacts,
    }
    errors = validate_manifest(task_dir, payload)
    if errors:
        raise ValueError("report manifest is invalid: " + "; ".join(errors))
    atomic_write_json(task_dir / "report_manifest.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--status", required=True, choices=sorted(FINAL_STATUSES))
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    try:
        payload = build_manifest(args.task_dir, args.subject, args.status, project_root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("REPORT_MANIFEST_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc
    print("REPORT_MANIFEST_OK")
    print(f"ARTIFACTS={len(payload['artifacts'])}")
    print(f"REPORT_MANIFEST={(args.task_dir.resolve() / 'report_manifest.json')}")


if __name__ == "__main__":
    main()
