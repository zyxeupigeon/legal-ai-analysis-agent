"""Shared helpers for report manifests and cross-run comparisons."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_SCHEMA_VERSION = "1.0"
DIFF_SCHEMA_VERSION = "1.0"
PROTOCOL_ID = "portable-agent-1.1"
FINAL_STATUSES = {"PASS", "PARTIAL", "FAIL"}
DYNAMIC_CATEGORIES = {
    "current_model_version",
    "current_product_version",
    "pricing",
    "operator",
    "policy_status",
}
REQUIRED_SESSION_CAPABILITIES = {
    "internet_search",
    "page_reading",
    "word_generation",
    "pdf_png_rendering",
    "direct_image_inspection",
}
SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key\s*[:=]|authorization\s*:|bearer\s+[A-Za-z0-9._-]{12,}|"
    r"sk-[A-Za-z0-9]{12,}|password\s*[:=]|client[_ -]?secret\s*[:=])"
)
URL_PATTERN = re.compile(
    r"https?://[^\s|<>\"'`()\[\]{}\uFF08\uFF09\u3010\u3011\u300A\u300B\u3008\u3009\u300C\u300D\u300E\u300F\uFF0C\u3002\uFF1B\uFF1A\u3001\uFF01\uFF1F\u201C\u201D\u2018\u2019]+",
    re.I,
)
URL_TRAILING_CHARACTERS = ".,;:!?\uFF0C\u3002\uFF1B\uFF1A\uFF01\uFF1F\u3001\uFF09\u3011\u300B\u300D\u300F"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def safe_subject(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ValueError("subject must not be empty")
    if len(normalized) > 200:
        raise ValueError("subject must be 200 characters or fewer")
    if SECRET_PATTERN.search(normalized):
        raise ValueError("subject appears to contain authentication material")
    return normalized


def subject_key(subject: str) -> str:
    normalized = safe_subject(subject).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def validate_session_capability_context(context: dict) -> list[str]:
    errors = []
    if context.get("visual_probe_verified") is not True:
        errors.append("task context visual probe was not verified")
    if context.get("document_self_test") != "READY":
        errors.append("task context document self-test is not READY")
    receipt_id = context.get("session_capability_receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        errors.append("task context capability receipt id is missing")
    capabilities = context.get("session_capabilities")
    if not isinstance(capabilities, dict):
        errors.append("task context session capabilities are missing")
    else:
        missing = sorted(
            name for name in REQUIRED_SESSION_CAPABILITIES
            if capabilities.get(name) != "READY"
        )
        if missing:
            errors.append("task context capabilities are not READY: " + ", ".join(missing))
    return errors


def verify_task_directory(task_dir: Path, project_root: Path) -> dict:
    task_dir = task_dir.resolve()
    project_root = project_root.resolve()
    output_root = (project_root / "agent_outputs").resolve()
    if not task_dir.is_relative_to(output_root):
        raise ValueError("task directory is outside this project agent_outputs")
    context = load_json(task_dir / "task_context.json")
    if context.get("session_gate") != "READY":
        raise ValueError("task context session gate must be READY")
    if context.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"task context protocol id must be {PROTOCOL_ID}")
    capability_errors = validate_session_capability_context(context)
    if capability_errors:
        raise ValueError("; ".join(capability_errors))
    if Path(str(context.get("project_root", ""))).resolve() != project_root:
        raise ValueError("task context project root does not match this project")
    if Path(str(context.get("output_root", ""))).resolve() != output_root:
        raise ValueError("task context output root does not match this project")
    if Path(str(context.get("task_output_dir", ""))).resolve() != task_dir:
        raise ValueError("task context task output directory does not match")
    return context


def safe_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("artifact path must be a non-empty string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"artifact path must stay inside the task directory: {value}")
    return path


def normalize_source_url(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    return normalized.rstrip(URL_TRAILING_CHARACTERS)


def extract_urls_from_text(text: str) -> list[str]:
    return sorted({
        normalized
        for match in URL_PATTERN.findall(text)
        if (normalized := normalize_source_url(match))
    })


def extract_source_urls(path: Path) -> list[str]:
    return extract_urls_from_text(path.read_text(encoding="utf-8"))


def claim_snapshot(claim: dict) -> dict:
    keys = (
        "claim_id",
        "claim_text",
        "claim_type",
        "category",
        "source_url",
        "source_tier",
        "accessed_at",
        "report_location",
        "included_in_report",
        "based_on_claim_ids",
    )
    return {key: claim.get(key) for key in keys if key in claim}


def load_claims(path: Path) -> dict[str, dict]:
    payload = load_json(path)
    claims = payload.get("claims")
    if payload.get("task_id") != path.parent.name:
        raise ValueError("claim_evidence.json task_id must match task directory")
    if payload.get("schema_version") != "1.0" or not isinstance(claims, list):
        raise ValueError("claim_evidence.json must use schema 1.0 and contain claims")
    result = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("claim_id"), str):
            raise ValueError("every claim must have a string claim_id")
        if claim["claim_id"] in result:
            raise ValueError(f"duplicate claim id: {claim['claim_id']}")
        result[claim["claim_id"]] = claim_snapshot(claim)
    return result


def trace_metrics(path: Path) -> dict:
    payload = load_json(path)
    stages: dict[str, dict] = {}
    total_seconds = 0.0
    failures = 0
    retries = 0
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        stage = str(event.get("stage", "other"))
        metrics = stages.setdefault(
            stage, {"duration_seconds": 0.0, "attempts": 0, "failures": 0, "retries": 0}
        )
        duration = event.get("duration_seconds")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            metrics["duration_seconds"] = round(metrics["duration_seconds"] + float(duration), 3)
            total_seconds += float(duration)
        metrics["attempts"] += 1
        if event.get("status") in {"failed", "blocked"}:
            metrics["failures"] += 1
            failures += 1
        if event.get("retry_of"):
            metrics["retries"] += 1
            retries += 1
    return {
        "total_duration_seconds": round(total_seconds, 3),
        "event_count": len(payload.get("events", [])),
        "failure_count": failures,
        "retry_count": retries,
        "observation_count": len(payload.get("observations", [])),
        "stages": dict(sorted(stages.items())),
    }


def unexpected_formal_artifacts(task_dir: Path) -> list[str]:
    unexpected = []
    for path in task_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(task_dir).as_posix()
        if path.suffix.lower() in {".docx", ".pdf"} and relative not in {
            "report.docx", "render/report.pdf"
        }:
            unexpected.append(relative)
        elif re.fullmatch(r"page-\d+\.png", path.name) and path.parent != task_dir / "render":
            unexpected.append(relative)
    return sorted(unexpected)


def validate_manifest(task_dir: Path, payload: dict | None = None) -> list[str]:
    errors: list[str] = []
    task_dir = task_dir.resolve()
    try:
        manifest = payload if payload is not None else load_json(task_dir / "report_manifest.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"report_manifest.json is unreadable or invalid: {exc}"]

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"report manifest schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if manifest.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"report manifest protocol_id must be {PROTOCOL_ID}")
    if manifest.get("task_id") != task_dir.name:
        errors.append("report manifest task_id does not match directory name")
    try:
        subject = safe_subject(str(manifest.get("subject", "")))
        if manifest.get("subject_key") != subject_key(subject):
            errors.append("report manifest subject_key does not match subject")
    except ValueError as exc:
        errors.append(f"report manifest subject is invalid: {exc}")
    if manifest.get("final_status") not in FINAL_STATUSES:
        errors.append("report manifest final_status must be PASS, PARTIAL, or FAIL")
    try:
        parse_timestamp(manifest.get("completed_at"))
    except ValueError as exc:
        errors.append(f"report manifest completed_at is invalid: {exc}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return errors + ["report manifest artifacts must be a list"]
    seen: set[str] = set()
    for index, artifact in enumerate(artifacts):
        label = f"report manifest artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{label} must be an object")
            continue
        try:
            relative = safe_relative_path(artifact.get("path"))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        relative_text = relative.as_posix()
        if relative_text in seen:
            errors.append(f"duplicate manifest artifact: {relative_text}")
            continue
        seen.add(relative_text)
        path = (task_dir / relative).resolve()
        if not path.is_relative_to(task_dir) or not path.is_file():
            errors.append(f"manifest artifact is missing: {relative_text}")
            continue
        if artifact.get("size_bytes") != path.stat().st_size:
            errors.append(f"manifest artifact size mismatch: {relative_text}")
        if artifact.get("sha256") != file_sha256(path):
            errors.append(f"manifest artifact hash mismatch: {relative_text}")
        if not isinstance(artifact.get("role"), str) or not artifact["role"].strip():
            errors.append(f"manifest artifact role is missing: {relative_text}")

    required = {
        "task_context.json",
        "execution_trace.json",
        "report.docx",
        "sources.md",
        "claim_evidence.json",
        "capability_declaration.md",
        "process_optimization_report.md",
        "report_diff.json",
        "report_diff.md",
        "render/report.pdf",
    }
    for relative in sorted(required - seen):
        errors.append(f"required manifest artifact is absent: {relative}")
    manifest_pages = {
        relative for relative in seen if re.fullmatch(r"render/page-\d+\.png", relative)
    }
    actual_pages = {
        path.relative_to(task_dir).as_posix()
        for path in (task_dir / "render").glob("page-*.png")
        if path.is_file()
    }
    if not manifest_pages:
        errors.append("report manifest must include at least one rendered page PNG")
    for relative in sorted(actual_pages - manifest_pages):
        errors.append(f"rendered page is absent from report manifest: {relative}")
    for relative in sorted(manifest_pages - actual_pages):
        errors.append(f"manifest rendered page does not exist: {relative}")
    for relative in unexpected_formal_artifacts(task_dir):
        errors.append(f"unexpected unmanifested formal artifact: {relative}")
    diff_path = task_dir / "report_diff.json"
    if diff_path.is_file():
        try:
            diff = load_json(diff_path)
            if manifest.get("subject_key") != diff.get("subject_key"):
                errors.append("report manifest subject does not match report diff")
            if manifest.get("baseline_task_id") != diff.get("baseline", {}).get("task_id"):
                errors.append("report manifest baseline_task_id does not match report diff")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"report diff cannot be bound to manifest: {exc}")
    return errors


def validate_diff(task_dir: Path, payload: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        diff = payload if payload is not None else load_json(task_dir / "report_diff.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"report_diff.json is unreadable or invalid: {exc}"]
    if diff.get("schema_version") != DIFF_SCHEMA_VERSION:
        errors.append(f"report diff schema_version must be {DIFF_SCHEMA_VERSION}")
    if diff.get("protocol_id") != PROTOCOL_ID:
        errors.append(f"report diff protocol_id must be {PROTOCOL_ID}")
    if diff.get("current_task_id") != task_dir.name:
        errors.append("report diff current_task_id does not match directory name")
    try:
        parse_timestamp(diff.get("generated_at"))
    except ValueError as exc:
        errors.append(f"report diff generated_at is invalid: {exc}")
    try:
        subject = safe_subject(str(diff.get("subject", "")))
        if diff.get("subject_key") != subject_key(subject):
            errors.append("report diff subject_key does not match subject")
    except ValueError as exc:
        errors.append(f"report diff subject is invalid: {exc}")
    baseline = diff.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("status") not in {"found", "not_found"}:
        errors.append("report diff baseline status must be found or not_found")
    elif baseline["status"] == "found":
        if not isinstance(baseline.get("task_id"), str) or not baseline["task_id"].strip():
            errors.append("report diff found baseline must include task_id")
        try:
            parse_timestamp(baseline.get("completed_at"))
        except ValueError as exc:
            errors.append(f"report diff baseline completed_at is invalid: {exc}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(baseline.get("manifest_sha256", ""))):
            errors.append("report diff baseline manifest_sha256 must be a SHA-256 digest")
    elif any(baseline.get(field) is not None for field in ("task_id", "completed_at", "manifest_sha256")):
        errors.append("report diff not_found baseline fields must be null")
    for field in ("claims", "analysis_conclusions", "dynamic_claims", "sources", "efficiency"):
        if not isinstance(diff.get(field), dict):
            errors.append(f"report diff {field} must be an object")
    for field in ("claims", "analysis_conclusions", "dynamic_claims"):
        comparison = diff.get(field)
        if isinstance(comparison, dict):
            for change_kind in ("added", "removed", "changed"):
                if not isinstance(comparison.get(change_kind), list):
                    errors.append(f"report diff {field}.{change_kind} must be a list")
    sources = diff.get("sources")
    if isinstance(sources, dict):
        for change_kind in ("added", "removed"):
            if not isinstance(sources.get(change_kind), list):
                errors.append(f"report diff sources.{change_kind} must be a list")
    efficiency = diff.get("efficiency")
    if isinstance(efficiency, dict):
        if not isinstance(efficiency.get("current"), dict):
            errors.append("report diff efficiency.current must be an object")
        if not isinstance(efficiency.get("stage_deltas"), dict):
            errors.append("report diff efficiency.stage_deltas must be an object")
    if not isinstance(diff.get("reminders"), list):
        errors.append("report diff reminders must be a list")
    return errors
