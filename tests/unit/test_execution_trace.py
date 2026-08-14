from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from execution_trace_lib import atomic_write_json, new_trace, trace_sha256, validate_trace


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECORDER = load_module("record_execution_event", "record_execution_event.py")
BUILDER = load_module("build_process_optimization_report", "build_process_optimization_report.py")


def task_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project_root = tmp_path.resolve()
    output_root = project_root / "agent_outputs"
    path = output_root / "trace_task"
    path.mkdir(parents=True)
    monkeypatch.setattr(RECORDER, "PROJECT_ROOT", project_root)
    (path / "task_context.json").write_text(
        json.dumps({
            "project_root": str(project_root),
            "output_root": str(output_root),
            "task_output_dir": str(path.resolve()),
        }),
        encoding="utf-8",
    )
    atomic_write_json(path / "execution_trace.json", new_trace(path.name))
    return path


def test_complete_trace_builds_hash_bound_optimization_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = task_dir(tmp_path, monkeypatch)
    for stage in (
        "target_scoping",
        "research",
        "evidence_analysis",
        "report_generation",
        "rendering",
        "visual_qa",
    ):
        started = argparse.Namespace(
            task_dir=output_dir,
            stage=stage,
            action=f"Complete {stage}",
            tool="test-tool",
            retry_of=None,
        )
        event_id = RECORDER.start_event(started)
        RECORDER.finish_event(argparse.Namespace(
            task_dir=output_dir,
            event_id=event_id,
            status="succeeded",
            note=None,
            artifact=None,
        ))

    RECORDER.add_observation(argparse.Namespace(
        task_dir=output_dir,
        stage="visual_qa",
        kind="optimization_recommendation",
        summary="Reuse verified source snapshots within one task",
        impact="Avoid duplicate reads while preserving source binding",
        resolution=None,
        priority="P1",
        expected_benefit="Shorter research time",
        implementation_cost="Low",
        risk="A stale snapshot could be reused across tasks",
        validation_method="Compare URL reads and source dates on the next run",
    ))
    RECORDER.finalize_trace(argparse.Namespace(task_dir=output_dir))

    trace_path = output_dir / "execution_trace.json"
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert validate_trace(
        payload,
        expected_task_id=output_dir.name,
        require_finalized=True,
        require_report_stages=True,
    ) == []

    report = BUILDER.build_report(
        trace_path,
        argparse.Namespace(
            subject="测试产品",
            agent="Test Agent",
            model="Test Model",
            report_file="report.docx",
            status="PASS",
        ),
    )
    assert f"执行轨迹SHA-256：{trace_sha256(trace_path)}" in report
    assert "## 2. 阶段记录与耗时" in report
    assert "## 7. 下一轮优化建议" in report

    with pytest.raises(ValueError, match="authentication material"):
        BUILDER.build_report(
            trace_path,
            argparse.Namespace(
                subject="api_key=should-not-be-recorded",
                agent="Test Agent",
                model="Test Model",
                report_file="report.docx",
                status="PASS",
            ),
        )



def test_trace_rejects_secret_like_notes_and_fabricated_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = task_dir(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="authentication material"):
        RECORDER.start_event(argparse.Namespace(
            task_dir=output_dir,
            stage="research",
            action="Use api_key=should-not-be-recorded",
            tool="test-tool",
            retry_of=None,
        ))

    event_id = RECORDER.start_event(argparse.Namespace(
        task_dir=output_dir,
        stage="research",
        action="Read public sources",
        tool="test-tool",
        retry_of=None,
    ))
    with pytest.raises(ValueError, match="task-relative paths"):
        RECORDER.finish_event(argparse.Namespace(
            task_dir=output_dir,
            event_id=event_id,
            status="succeeded",
            note=None,
            artifact=[str(tmp_path / "outside.txt")],
        ))


    trace_path = output_dir / "execution_trace.json"
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert payload["events"][1]["status"] == "running"
    payload["events"][0]["duration_seconds"] = 99
    errors = validate_trace(payload)
    assert "events[0].duration_seconds does not match timestamps" in errors



def test_finalize_rejects_missing_report_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = task_dir(tmp_path, monkeypatch)
    RECORDER.add_observation(argparse.Namespace(
        task_dir=output_dir,
        stage="other",
        kind="optimization_recommendation",
        summary="Keep the complete stage contract",
        impact="Missing stages would make timing claims incomplete",
        resolution=None,
        priority="P0",
        expected_benefit="Auditable reports",
        implementation_cost="Low",
        risk="More event recording calls",
        validation_method="Finalize a complete synthetic trace",
    ))
    with pytest.raises(ValueError, match="lacks successful required stages"):
        RECORDER.finalize_trace(argparse.Namespace(task_dir=output_dir))


def test_recorder_rejects_task_directory_outside_current_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    (project_root / "agent_outputs").mkdir(parents=True)
    outside = tmp_path / "outside_task"
    outside.mkdir()
    monkeypatch.setattr(RECORDER, "PROJECT_ROOT", project_root)
    (outside / "task_context.json").write_text(
        json.dumps({
            "project_root": str(project_root),
            "output_root": str(project_root / "agent_outputs"),
            "task_output_dir": str(outside),
        }),
        encoding="utf-8",
    )
    atomic_write_json(outside / "execution_trace.json", new_trace(outside.name))
    with pytest.raises(ValueError, match="outside this project agent_outputs"):
        RECORDER.load_bound_trace(outside)

def test_finalized_trace_requires_failure_observation_for_failed_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = task_dir(tmp_path, monkeypatch)
    failed_event_id = None
    for stage in (
        "target_scoping",
        "research",
        "evidence_analysis",
        "report_generation",
        "rendering",
        "visual_qa",
    ):
        event_id = RECORDER.start_event(argparse.Namespace(
            task_dir=output_dir,
            stage=stage,
            action=f"Complete {stage}",
            tool="test-tool",
            retry_of=None,
        ))
        status = "failed" if stage == "rendering" else "succeeded"
        RECORDER.finish_event(argparse.Namespace(
            task_dir=output_dir,
            event_id=event_id,
            status=status,
            note="Synthetic renderer failure" if status == "failed" else None,
            artifact=None,
        ))
        if status == "failed":
            failed_event_id = event_id
            retry_id = RECORDER.start_event(argparse.Namespace(
                task_dir=output_dir,
                stage="rendering",
                action="Retry rendering",
                tool="test-tool",
                retry_of=failed_event_id,
            ))
            RECORDER.finish_event(argparse.Namespace(
                task_dir=output_dir,
                event_id=retry_id,
                status="succeeded",
                note=None,
                artifact=None,
            ))
    RECORDER.add_observation(argparse.Namespace(
        task_dir=output_dir,
        stage="visual_qa",
        kind="optimization_recommendation",
        summary="Keep failure records complete",
        impact="Optimization reports remain truthful",
        resolution=None,
        priority="P0",
        expected_benefit="No omitted retries",
        implementation_cost="Low",
        risk="More trace entries",
        validation_method="Finalize a trace with a failed render attempt",
    ))

    with pytest.raises(ValueError, match="failure observation"):
        RECORDER.finalize_trace(argparse.Namespace(task_dir=output_dir))

    RECORDER.add_observation(argparse.Namespace(
        task_dir=output_dir,
        stage="rendering",
        kind="failure",
        summary="The first render attempt failed",
        impact="A retry was required",
        resolution="Used the canonical renderer",
        priority=None,
        expected_benefit=None,
        implementation_cost=None,
        risk=None,
        validation_method=None,
    ))
    RECORDER.finalize_trace(argparse.Namespace(task_dir=output_dir))
