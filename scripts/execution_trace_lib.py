"""Shared helpers for deterministic, agent-independent execution traces."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
EVENT_STATUSES = {"running", "succeeded", "failed", "blocked", "skipped"}
TERMINAL_STATUSES = EVENT_STATUSES - {"running"}
STAGES = {
    "workspace_allocation", "target_scoping", "research", "evidence_analysis",
    "report_generation", "rendering", "visual_qa", "remediation", "other",
}
REQUIRED_REPORT_STAGES = {
    "workspace_allocation", "target_scoping", "research", "evidence_analysis",
    "report_generation", "rendering", "visual_qa",
}
OBSERVATION_KINDS = {
    "failure", "bottleneck", "ineffective_step", "quality_risk",
    "reusable_practice", "optimization_recommendation",
}
PRIORITIES = {"P0", "P1", "P2"}
SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key\s*[:=]|authorization\s*:|bearer\s+[A-Za-z0-9._-]{12,}|"
    r"sk-[A-Za-z0-9]{12,}|password\s*[:=]|client[_ -]?secret\s*[:=])"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must include UTC offset")
    return parsed


def ensure_safe_text(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    if SECRET_PATTERN.search(value):
        raise ValueError(f"{field} appears to contain authentication material")
    return value


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def new_trace(task_id: str, created_at: str | None = None) -> dict:
    timestamp = created_at or utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "finalized_at": None,
        "events": [{
            "event_id": "E0001",
            "sequence": 1,
            "stage": "workspace_allocation",
            "action": "Create an isolated task workspace bound to this project copy",
            "tool": "scripts/create_task_workspace.py",
            "started_at": timestamp,
            "ended_at": timestamp,
            "duration_seconds": 0.0,
            "status": "succeeded",
            "retry_of": None,
            "note": "Task context and execution trace initialized.",
            "artifacts": ["task_context.json", "execution_trace.json"],
        }],
        "observations": [],
    }


def trace_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_task_binding(task_dir: Path, project_root: Path) -> dict:
    task_dir = task_dir.resolve()
    project_root = project_root.resolve()
    output_root = (project_root / "agent_outputs").resolve()
    if not task_dir.is_relative_to(output_root):
        raise ValueError("task directory is outside this project agent_outputs")
    context = json.loads((task_dir / "task_context.json").read_text(encoding="utf-8"))
    expected = {
        "project_root": project_root,
        "output_root": output_root,
        "task_output_dir": task_dir,
    }
    for key, expected_path in expected.items():
        value = context.get(key)
        if not isinstance(value, str):
            raise ValueError(f"task context {key} does not match this project copy")
        candidate = Path(value)
        if not candidate.is_absolute() or candidate.resolve() != expected_path:
            raise ValueError(f"task context {key} does not match this project copy")
    return context



def validate_trace(
    payload: object,
    *,
    expected_task_id: str | None = None,
    require_finalized: bool = False,
    require_report_stages: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["execution trace root must be an object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"execution trace schema_version must be {SCHEMA_VERSION}")
    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        errors.append("execution trace task_id is required")
    elif expected_task_id is not None and task_id != expected_task_id:
        errors.append("execution trace task_id does not match task directory")

    meta_times: dict[str, datetime] = {}
    for key in ("created_at", "updated_at"):
        try:
            meta_times[key] = parse_timestamp(payload.get(key))
        except (TypeError, ValueError):
            errors.append(f"execution trace {key} must be a UTC ISO-8601 timestamp")
    finalized_at = payload.get("finalized_at")
    if finalized_at is not None:
        try:
            meta_times["finalized_at"] = parse_timestamp(finalized_at)
        except (TypeError, ValueError):
            errors.append("execution trace finalized_at must be a UTC ISO-8601 timestamp")
    elif require_finalized:
        errors.append("execution trace is not finalized")
    if {"created_at", "updated_at"} <= meta_times.keys():
        if meta_times["updated_at"] < meta_times["created_at"]:
            errors.append("execution trace updated_at precedes created_at")
    if "finalized_at" in meta_times and "updated_at" in meta_times:
        if meta_times["finalized_at"] != meta_times["updated_at"]:
            errors.append("finalized execution trace must have matching finalized_at and updated_at")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        errors.append("execution trace must contain at least one event")
        events = []
    seen_event_ids: set[str] = set()
    seen_started: list[datetime] = []
    succeeded_stages: set[str] = set()
    event_statuses: dict[str, str] = {}
    for index, event in enumerate(events, start=1):
        label = f"events[{index - 1}]"
        if not isinstance(event, dict):
            errors.append(f"{label} must be an object")
            continue
        event_id = event.get("event_id")
        expected_id = f"E{index:04d}"
        if event_id != expected_id or event_id in seen_event_ids:
            errors.append(f"{label}.event_id must be unique and equal {expected_id}")
        elif isinstance(event_id, str):
            seen_event_ids.add(event_id)
        if event.get("sequence") != index:
            errors.append(f"{label}.sequence must equal {index}")
        stage = event.get("stage")
        if stage not in STAGES:
            errors.append(f"{label}.stage is invalid")
        status = event.get("status")
        if status not in EVENT_STATUSES:
            errors.append(f"{label}.status is invalid")
        elif isinstance(event_id, str):
            event_statuses[event_id] = status
        if status == "succeeded" and isinstance(stage, str):
            succeeded_stages.add(stage)
        for key in ("action", "tool"):
            value = event.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}.{key} is required")
            elif SECRET_PATTERN.search(value):
                errors.append(f"{label}.{key} appears to contain authentication material")
        try:
            started_at = parse_timestamp(event.get("started_at"))
            seen_started.append(started_at)
        except (TypeError, ValueError):
            errors.append(f"{label}.started_at must be a UTC ISO-8601 timestamp")
            started_at = None
        ended_at = event.get("ended_at")
        duration = event.get("duration_seconds")
        if status == "running":
            if ended_at is not None or duration is not None:
                errors.append(f"{label} running event cannot have end time or duration")
            if finalized_at is not None:
                errors.append(f"{label} is still running in a finalized trace")
        else:
            try:
                parsed_end = parse_timestamp(ended_at)
                if started_at is not None and parsed_end < started_at:
                    errors.append(f"{label}.ended_at precedes started_at")
                if not isinstance(duration, (int, float)) or duration < 0:
                    errors.append(f"{label}.duration_seconds must be non-negative")
                elif started_at is not None:
                    actual = round((parsed_end - started_at).total_seconds(), 3)
                    if abs(float(duration) - actual) > 0.01:
                        errors.append(f"{label}.duration_seconds does not match timestamps")
            except (TypeError, ValueError):
                errors.append(f"{label}.ended_at must be a UTC ISO-8601 timestamp")
        retry_of = event.get("retry_of")
        if retry_of is not None and retry_of not in seen_event_ids:
            errors.append(f"{label}.retry_of must reference an earlier event")
        artifacts = event.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append(f"{label}.artifacts must be a list")
        else:
            for artifact in artifacts:
                if not isinstance(artifact, str) or not artifact.strip():
                    errors.append(f"{label}.artifacts contains an invalid path")
                    continue
                path = Path(artifact)
                if path.is_absolute() or ".." in path.parts:
                    errors.append(f"{label}.artifacts must use task-relative paths")
        note = event.get("note")
        if note is not None and (not isinstance(note, str) or SECRET_PATTERN.search(note)):
            errors.append(f"{label}.note is invalid or contains authentication material")

    if seen_started != sorted(seen_started):
        errors.append("execution trace events are not ordered by start time")
    for event in events:
        if isinstance(event, dict) and event.get("retry_of"):
            if event_statuses.get(event["retry_of"]) not in {"failed", "blocked"}:
                errors.append(f"{event.get('event_id')} retries an event that did not fail or block")
    if require_report_stages:
        missing = sorted(REQUIRED_REPORT_STAGES - succeeded_stages)
        if missing:
            errors.append("execution trace lacks successful required stages: " + ", ".join(missing))

    observations = payload.get("observations")
    if not isinstance(observations, list):
        errors.append("execution trace observations must be a list")
        observations = []
    for index, observation in enumerate(observations, start=1):
        label = f"observations[{index - 1}]"
        if not isinstance(observation, dict):
            errors.append(f"{label} must be an object")
            continue
        if observation.get("observation_id") != f"O{index:04d}":
            errors.append(f"{label}.observation_id must equal O{index:04d}")
        if observation.get("sequence") != index:
            errors.append(f"{label}.sequence must equal {index}")
        if observation.get("kind") not in OBSERVATION_KINDS:
            errors.append(f"{label}.kind is invalid")
        if observation.get("stage") not in STAGES:
            errors.append(f"{label}.stage is invalid")
        try:
            parse_timestamp(observation.get("timestamp"))
        except (TypeError, ValueError):
            errors.append(f"{label}.timestamp must be a UTC ISO-8601 timestamp")
        for key in ("summary", "impact"):
            value = observation.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}.{key} is required")
            elif SECRET_PATTERN.search(value):
                errors.append(f"{label}.{key} appears to contain authentication material")
        resolution = observation.get("resolution")
        if resolution is not None and (
            not isinstance(resolution, str) or SECRET_PATTERN.search(resolution)
        ):
            errors.append(f"{label}.resolution is invalid or contains authentication material")
        if observation.get("kind") == "optimization_recommendation":
            if observation.get("priority") not in PRIORITIES:
                errors.append(f"{label}.priority must be P0, P1, or P2")
            for key in ("expected_benefit", "implementation_cost", "risk", "validation_method"):
                if not isinstance(observation.get(key), str) or not observation[key].strip():
                    errors.append(f"{label}.{key} is required for optimization recommendations")
                elif SECRET_PATTERN.search(observation[key]):
                    errors.append(f"{label}.{key} appears to contain authentication material")

    if require_finalized:
        failed_events = [
            event for event in events
            if isinstance(event, dict) and event.get("status") in {"failed", "blocked"}
        ]
        recorded_failures = [
            item for item in observations
            if isinstance(item, dict) and item.get("kind") == "failure"
        ]
        if failed_events and not recorded_failures:
            errors.append(
                "finalized execution trace with failed or blocked events must include a failure observation"
            )
    if require_finalized and not any(
        isinstance(item, dict) and item.get("kind") == "optimization_recommendation"
        for item in observations
    ):
        errors.append("finalized execution trace must include an optimization recommendation")
    return errors
