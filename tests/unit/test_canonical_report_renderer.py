from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import render_report as renderer


def configure_task(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    task_dir = project_root / "agent_outputs" / "task-1"
    task_dir.mkdir(parents=True)
    (task_dir / "report.docx").write_bytes(b"canonical-docx")
    (task_dir / "execution_trace.json").write_text(
        json.dumps({"events": []}), encoding="utf-8"
    )
    monkeypatch.setattr(renderer, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(renderer, "verify_task_binding", lambda *args: {})
    return task_dir


def test_renderer_writes_only_canonical_layout(monkeypatch, tmp_path) -> None:
    task_dir = configure_task(monkeypatch, tmp_path)
    events = []
    monkeypatch.setattr(renderer, "start_event", lambda args: events.append(("start", args)) or "E0002")
    monkeypatch.setattr(renderer, "finish_event", lambda args: events.append(("finish", args)))
    monkeypatch.setattr(renderer, "add_observation", lambda args: events.append(("observe", args)))
    monkeypatch.setattr(renderer, "latest_failed_render_event", lambda task: None)

    def fake_word_to_pdf(docx: Path, pdf: Path) -> bool:
        pdf.write_bytes(b"pdf")
        return True

    def fake_pages(pdf: Path, output: Path):
        page = output / "page-001.png"
        page.write_bytes(b"png")
        return [page], "test-renderer"

    monkeypatch.setattr(renderer, "word_to_pdf", fake_word_to_pdf)
    monkeypatch.setattr(renderer, "render_pdf_pages", fake_pages)

    pdf, pages, name = renderer.render_task(task_dir)

    assert pdf == task_dir / "render" / "report.pdf"
    assert pages == [task_dir / "render" / "page-001.png"]
    assert name == "test-renderer"
    assert sorted(path.relative_to(task_dir).as_posix() for path in task_dir.rglob("*.docx")) == [
        "report.docx"
    ]
    assert sorted(path.relative_to(task_dir).as_posix() for path in task_dir.rglob("*.pdf")) == [
        "render/report.pdf"
    ]
    assert [kind for kind, _ in events] == ["start", "finish"]
    assert events[-1][1].status == "succeeded"


def test_renderer_failure_is_recorded_before_exit(monkeypatch, tmp_path) -> None:
    task_dir = configure_task(monkeypatch, tmp_path)
    events = []
    monkeypatch.setattr(renderer, "start_event", lambda args: "E0002")
    monkeypatch.setattr(renderer, "finish_event", lambda args: events.append(("finish", args)))
    monkeypatch.setattr(renderer, "add_observation", lambda args: events.append(("observe", args)))
    monkeypatch.setattr(renderer, "latest_failed_render_event", lambda task: None)
    monkeypatch.setattr(renderer, "word_to_pdf", lambda docx, pdf: False)

    with pytest.raises(RuntimeError, match="DOCX-to-PDF conversion failed"):
        renderer.render_task(task_dir)

    assert [kind for kind, _ in events] == ["finish", "observe"]
    assert events[0][1].status == "failed"
    assert events[1][1].kind == "failure"
