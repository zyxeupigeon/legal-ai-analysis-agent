"""Allocate a task output directory anchored to this project copy."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "agent_outputs"
PROTOCOL_ID = "portable-agent-0.4"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


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


def allocate(task_id: str) -> Path:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("task id must use 1-80 ASCII letters, digits, underscores, or hyphens")
    verify_project_binding()
    output_dir = (OUTPUT_ROOT / task_id).resolve()
    if not output_dir.is_relative_to(OUTPUT_ROOT.resolve()):
        raise RuntimeError("task output path escaped agent_outputs")
    output_dir.mkdir(parents=True, exist_ok=False)
    context = {
        "protocol_id": PROTOCOL_ID,
        "project_root": str(PROJECT_ROOT),
        "output_root": str(OUTPUT_ROOT.resolve()),
        "task_output_dir": str(output_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "task_context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    try:
        output_dir = allocate(args.task_id)
    except (FileExistsError, RuntimeError, ValueError) as exc:
        print("TASK_WORKSPACE_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc
    print("TASK_WORKSPACE_OK")
    print(f"PROJECT_ROOT={PROJECT_ROOT}")
    print(f"TASK_OUTPUT_DIR={output_dir}")


if __name__ == "__main__":
    main()
