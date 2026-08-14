from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPERS_PATH = Path(__file__).with_name("test_report_versioning.py")
SPEC = importlib.util.spec_from_file_location("report_versioning_test_helpers", HELPERS_PATH)
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


def test_cli_builds_first_baseline_then_selects_it_for_second_run() -> None:
    unique = uuid.uuid4().hex[:12]
    first_id = f"cli_{unique}_first"
    second_id = f"cli_{unique}_second"
    subject = f"CLI测试产品-{unique}"
    first = HELPERS.create_task(
        REPO_ROOT,
        first_id,
        price="官方价格为4元每页",
        source_url=f"https://official.example/{unique}/v1",
    )
    second = REPO_ROOT / "agent_outputs" / second_id
    try:
        result = run_script(
            "scripts/compare_report_versions.py", str(first), "--subject", subject
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "BASELINE=NONE" in result.stdout
        result = run_script(
            "scripts/build_report_manifest.py",
            str(first),
            "--subject",
            subject,
            "--status",
            "PASS",
        )
        assert result.returncode == 0, result.stdout + result.stderr

        HELPERS.create_task(
            REPO_ROOT,
            second_id,
            price="官方价格为5元每页",
            source_url=f"https://official.example/{unique}/v2",
            duration_multiplier=2,
        )
        result = run_script(
            "scripts/compare_report_versions.py", str(second), "--subject", subject
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"BASELINE={first_id}" in result.stdout
        payload = json.loads((second / "report_diff.json").read_text(encoding="utf-8"))
        assert payload["baseline"]["manifest_sha256"]
        assert payload["dynamic_claims"]["changed"][0]["claim_id"] == "C001"
    finally:
        for path in (first, second):
            if path.is_dir() and path.resolve().parent == (REPO_ROOT / "agent_outputs").resolve():
                shutil.rmtree(path)
