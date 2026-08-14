"""Render task-local report.docx to the canonical PDF and page PNG layout."""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from execution_trace_lib import verify_task_binding
from record_execution_event import add_observation, finish_event, start_event
from self_test_document_pipeline import word_to_pdf


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def render_pdf_pages(pdf_path: Path, output_dir: Path) -> tuple[list[Path], str]:
    for module_name in ("pymupdf", "fitz"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        document = module.open(pdf_path)
        try:
            if len(document) < 1:
                raise RuntimeError("rendered PDF has no pages")
            pages = []
            for index, page in enumerate(document, start=1):
                path = output_dir / f"page-{index:03d}.png"
                pixmap = page.get_pixmap(matrix=module.Matrix(1.5, 1.5), alpha=False)
                pixmap.save(path)
                pages.append(path)
            return pages, module_name
        finally:
            document.close()

    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise RuntimeError("no PDF-to-PNG renderer is available")
    prefix = output_dir / "page"
    result = subprocess.run(
        [renderer, "-png", "-r", "150", str(pdf_path), str(prefix)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"pdftoppm failed with exit code {result.returncode}: {detail}")
    pages = sorted(output_dir.glob("page-*.png"))
    if not pages:
        raise RuntimeError("pdftoppm produced no page PNG files")
    normalized = []
    for index, source in enumerate(pages, start=1):
        destination = output_dir / f"page-{index:03d}.png"
        if source != destination:
            source.replace(destination)
        normalized.append(destination)
    return normalized, "pdftoppm"


def replace_render_directory(task_dir: Path, pending: Path) -> Path:
    final = task_dir / "render"
    if final.exists():
        unexpected = [
            path for path in final.rglob("*")
            if path.is_file()
            and path.name != "report.pdf"
            and not path.name.startswith("page-")
        ]
        if unexpected:
            raise RuntimeError("existing render directory contains unexpected files; refusing overwrite")
        backup = task_dir / ".render_previous"
        if backup.exists():
            raise RuntimeError("stale .render_previous directory exists; inspect it before retrying")
        final.replace(backup)
        try:
            pending.replace(final)
        except Exception:
            backup.replace(final)
            raise
        shutil.rmtree(backup)
    else:
        pending.replace(final)
    return final


def latest_failed_render_event(task_dir: Path) -> str | None:
    trace = json.loads((task_dir / "execution_trace.json").read_text(encoding="utf-8"))
    failed = [
        event for event in trace.get("events", [])
        if event.get("stage") == "rendering" and event.get("status") in {"failed", "blocked"}
    ]
    return failed[-1]["event_id"] if failed else None


def render_task(task_dir: Path) -> tuple[Path, list[Path], str]:
    task_dir = task_dir.resolve()
    verify_task_binding(task_dir, PROJECT_ROOT)
    report = task_dir / "report.docx"
    if not report.is_file() or report.stat().st_size == 0:
        raise ValueError("canonical report.docx is missing or empty")

    retry_of = latest_failed_render_event(task_dir)
    event_id = start_event(argparse.Namespace(
        task_dir=task_dir,
        stage="rendering",
        action="Render canonical report.docx to render/report.pdf and all page PNG files",
        tool="scripts/render_report.py",
        retry_of=retry_of,
    ))
    pending = Path(tempfile.mkdtemp(prefix=".render_pending_", dir=task_dir))
    try:
        pdf = pending / "report.pdf"
        if not word_to_pdf(report, pdf):
            raise RuntimeError("DOCX-to-PDF conversion failed")
        pages, renderer = render_pdf_pages(pdf, pending)
        if not pdf.is_file() or pdf.stat().st_size == 0:
            raise RuntimeError("rendered PDF is missing or empty")
        if any(not page.is_file() or page.stat().st_size == 0 for page in pages):
            raise RuntimeError("one or more rendered page PNG files are missing or empty")
        final = replace_render_directory(task_dir, pending)
        final_pages = sorted(final.glob("page-*.png"))
        finish_event(argparse.Namespace(
            task_dir=task_dir,
            event_id=event_id,
            status="succeeded",
            note=f"Rendered {len(final_pages)} page(s) with {renderer}.",
            artifact=["render/report.pdf", *(f"render/{page.name}" for page in final_pages)],
        ))
        return final / "report.pdf", final_pages, renderer
    except Exception as exc:
        if pending.exists():
            shutil.rmtree(pending, ignore_errors=True)
        finish_event(argparse.Namespace(
            task_dir=task_dir,
            event_id=event_id,
            status="failed",
            note=f"{type(exc).__name__}: {exc}",
            artifact=None,
        ))
        add_observation(argparse.Namespace(
            task_dir=task_dir,
            stage="rendering",
            kind="failure",
            summary="Canonical report rendering attempt failed",
            impact="The report cannot pass or proceed to visual QA until rendering succeeds",
            resolution="Correct the reported low-risk cause and rerun scripts/render_report.py; the retry is linked automatically",
            priority=None,
            expected_benefit=None,
            implementation_cost=None,
            risk=None,
            validation_method=None,
        ))
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    args = parser.parse_args()
    try:
        pdf, pages, renderer = render_task(args.task_dir)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print("REPORT_RENDER_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc
    print("REPORT_RENDER_OK")
    print(f"PDF={pdf}")
    print(f"PAGES={len(pages)}")
    print(f"RENDERER={renderer}")


if __name__ == "__main__":
    main()
