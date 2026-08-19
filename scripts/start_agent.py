"""Windows-friendly launcher that avoids downloaded .ps1 execution-policy failures."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "portable-agent-1.1"


def executable_command(path: str, *args: str) -> list[str]:
    if Path(path).suffix.lower() in {".cmd", ".bat"}:
        return ["cmd.exe", "/d", "/c", path, *args]
    return [path, *args]


def resolve_agent(name: str) -> str | None:
    path = shutil.which(name)
    if not path:
        return None
    try:
        result = subprocess.run(
            executable_command(path, "--version"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    return path if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-Agent", "--agent", choices=("auto", "claude", "opencode", "codex", "gemini"), default="auto")
    parser.add_argument("-CheckOnly", "--check-only", action="store_true")
    parser.add_argument("-SelfTest", "--self-test", action="store_true")
    args = parser.parse_args()
    if args.check_only and args.self_test:
        parser.error("choose either -CheckOnly or -SelfTest")

    os.chdir(PROJECT_ROOT)
    os.environ["LEGAL_AI_PROJECT_ROOT"] = str(PROJECT_ROOT)
    os.environ["LEGAL_AI_OUTPUT_ROOT"] = str(PROJECT_ROOT / "agent_outputs")
    os.environ["LEGAL_AI_PROTOCOL_ID"] = PROTOCOL_ID

    print("Legal AI Analysis Project - Agent launcher")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Output root: {PROJECT_ROOT / 'agent_outputs'}")
    sys.stdout.flush()
    preflight = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "check_agent_workspace.py")],
        check=False,
    )
    if preflight.returncode:
        print("Workspace preflight failed. Agent launch stopped.", file=sys.stderr)
        return preflight.returncode

    if args.self_test:
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "self_test_document_pipeline.py")],
            check=False,
        ).returncode

    launchers = {name: resolve_agent(name) for name in ("claude", "opencode", "codex", "gemini")}
    print("\nDetected agents:")
    for name, path in launchers.items():
        print(f"- {name}: {'available' if path else 'not installed'}")
    if args.check_only:
        print("AGENT_LAUNCH_CHECK_OK")
        return 0

    selected = args.agent
    if selected == "auto":
        selected = next((name for name in ("claude", "opencode", "codex", "gemini") if launchers[name]), "")
    if not selected or not launchers.get(selected):
        print("No supported Agent launcher was found. Install and sign in to Claude Code, OpenCode, Codex CLI, or Gemini CLI.", file=sys.stderr)
        return 1

    print(f"\nLaunching: {selected}")
    print(f"This session is bound to: {PROJECT_ROOT}")
    print("After the Agent opens, it must declare SESSION_PREFLIGHT_READY or SESSION_PREFLIGHT_BLOCKED before any task allocation or report work.\n")
    extra = (str(PROJECT_ROOT),) if selected == "opencode" else ()
    return subprocess.call(executable_command(launchers[selected], *extra))


if __name__ == "__main__":
    raise SystemExit(main())