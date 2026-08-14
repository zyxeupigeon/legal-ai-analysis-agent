"""Record verifiable task stages and observations without binding to a specific agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from execution_trace_lib import (
    OBSERVATION_KINDS,
    PRIORITIES,
    STAGES,
    TERMINAL_STATUSES,
    atomic_write_json,
    ensure_safe_text,
    parse_timestamp,
    utc_now,
    verify_task_binding,
    validate_trace,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_bound_trace(task_dir: Path) -> tuple[Path, dict]:
    task_dir = task_dir.resolve()
    verify_task_binding(task_dir, PROJECT_ROOT)
    trace_path = task_dir / "execution_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    errors = validate_trace(trace, expected_task_id=task_dir.name)
    if errors:
        raise ValueError("invalid execution trace: " + "; ".join(errors))
    if trace.get("finalized_at") is not None:
        raise ValueError("execution trace is finalized and cannot be changed")
    return trace_path, trace



def save_trace(trace_path: Path, trace: dict, *, finalized: bool = False) -> None:
    errors = validate_trace(
        trace,
        expected_task_id=trace_path.parent.name,
        require_finalized=finalized,
        require_report_stages=finalized,
    )
    if errors:
        raise ValueError("refusing to write invalid execution trace: " + "; ".join(errors))
    atomic_write_json(trace_path, trace)


def start_event(args: argparse.Namespace) -> str:
    trace_path, trace = load_bound_trace(args.task_dir)
    timestamp = utc_now()
    event_id = f"E{len(trace['events']) + 1:04d}"
    if args.retry_of:
        previous = next(
            (item for item in trace["events"] if item["event_id"] == args.retry_of), None
        )
        if previous is None or previous["status"] not in {"failed", "blocked"}:
            raise ValueError("retry-of must reference an earlier failed or blocked event")
    trace["events"].append({
        "event_id": event_id,
        "sequence": len(trace["events"]) + 1,
        "stage": args.stage,
        "action": ensure_safe_text(args.action, "action"),
        "tool": ensure_safe_text(args.tool, "tool"),
        "started_at": timestamp,
        "ended_at": None,
        "duration_seconds": None,
        "status": "running",
        "retry_of": args.retry_of,
        "note": None,
        "artifacts": [],
    })
    trace["updated_at"] = timestamp
    save_trace(trace_path, trace)
    return event_id


def finish_event(args: argparse.Namespace) -> str:
    trace_path, trace = load_bound_trace(args.task_dir)
    event = next((item for item in trace["events"] if item["event_id"] == args.event_id), None)
    if event is None or event["status"] != "running":
        raise ValueError("event-id must reference a running event")
    timestamp = utc_now()
    event["ended_at"] = timestamp
    event["duration_seconds"] = round(
        (parse_timestamp(timestamp) - parse_timestamp(event["started_at"])).total_seconds(), 3
    )
    event["status"] = args.status
    event["note"] = ensure_safe_text(args.note, "note") if args.note else None
    event["artifacts"] = args.artifact or []
    trace["updated_at"] = timestamp
    save_trace(trace_path, trace)
    return event["event_id"]


def add_observation(args: argparse.Namespace) -> str:
    trace_path, trace = load_bound_trace(args.task_dir)
    timestamp = utc_now()
    observation_id = f"O{len(trace['observations']) + 1:04d}"
    observation = {
        "observation_id": observation_id,
        "sequence": len(trace["observations"]) + 1,
        "timestamp": timestamp,
        "stage": args.stage,
        "kind": args.kind,
        "summary": ensure_safe_text(args.summary, "summary"),
        "impact": ensure_safe_text(args.impact, "impact"),
        "resolution": ensure_safe_text(args.resolution, "resolution") if args.resolution else None,
        "priority": args.priority,
        "expected_benefit": args.expected_benefit,
        "implementation_cost": args.implementation_cost,
        "risk": args.risk,
        "validation_method": args.validation_method,
    }
    if args.kind == "optimization_recommendation":
        required = {
            "priority": args.priority,
            "expected-benefit": args.expected_benefit,
            "implementation-cost": args.implementation_cost,
            "risk": args.risk,
            "validation-method": args.validation_method,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError("optimization recommendation is missing: " + ", ".join(missing))
        for key in ("expected_benefit", "implementation_cost", "risk", "validation_method"):
            observation[key] = ensure_safe_text(observation[key], key)
    trace["observations"].append(observation)
    trace["updated_at"] = timestamp
    save_trace(trace_path, trace)
    return observation_id


def finalize_trace(args: argparse.Namespace) -> None:
    trace_path, trace = load_bound_trace(args.task_dir)
    errors = validate_trace(
        trace,
        expected_task_id=args.task_dir.resolve().name,
        require_report_stages=True,
    )
    running = [event["event_id"] for event in trace["events"] if event["status"] == "running"]
    if running:
        errors.append("running events remain: " + ", ".join(running))
    if not any(item["kind"] == "optimization_recommendation" for item in trace["observations"]):
        errors.append("at least one optimization recommendation is required")
    if errors:
        raise ValueError("cannot finalize execution trace: " + "; ".join(errors))
    timestamp = utc_now()
    trace["updated_at"] = timestamp
    trace["finalized_at"] = timestamp
    save_trace(trace_path, trace, finalized=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    start.add_argument("task_dir", type=Path)
    start.add_argument("--stage", required=True, choices=sorted(STAGES))
    start.add_argument("--action", required=True)
    start.add_argument("--tool", required=True)
    start.add_argument("--retry-of")

    finish = commands.add_parser("finish")
    finish.add_argument("task_dir", type=Path)
    finish.add_argument("--event-id", required=True)
    finish.add_argument("--status", required=True, choices=sorted(TERMINAL_STATUSES))
    finish.add_argument("--note")
    finish.add_argument("--artifact", action="append")

    observe = commands.add_parser("observe")
    observe.add_argument("task_dir", type=Path)
    observe.add_argument("--stage", required=True, choices=sorted(STAGES))
    observe.add_argument("--kind", required=True, choices=sorted(OBSERVATION_KINDS))
    observe.add_argument("--summary", required=True)
    observe.add_argument("--impact", required=True)
    observe.add_argument("--resolution")
    observe.add_argument("--priority", choices=sorted(PRIORITIES))
    observe.add_argument("--expected-benefit")
    observe.add_argument("--implementation-cost")
    observe.add_argument("--risk")
    observe.add_argument("--validation-method")

    finalize = commands.add_parser("finalize")
    finalize.add_argument("task_dir", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "start":
            print(f"EXECUTION_EVENT_STARTED event_id={start_event(args)}")
        elif args.command == "finish":
            print(f"EXECUTION_EVENT_FINISHED event_id={finish_event(args)}")
        elif args.command == "observe":
            print(f"EXECUTION_OBSERVATION_RECORDED observation_id={add_observation(args)}")
        else:
            finalize_trace(args)
            print("EXECUTION_TRACE_FINALIZED")
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        print("EXECUTION_TRACE_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
