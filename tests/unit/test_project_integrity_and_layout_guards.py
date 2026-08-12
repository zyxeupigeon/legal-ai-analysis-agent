import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate_portable_agent_output.py"
SPEC = importlib.util.spec_from_file_location("validate_portable_agent_output", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_project_integrity_detects_file_changed_after_task_start(tmp_path: Path) -> None:
    protected = tmp_path / "evaluations" / "profile.json"
    protected.parent.mkdir()
    protected.write_text('{"required_report_label": "original"}', encoding="utf-8")
    context = {
        "protected_project_hashes": {
            "evaluations/profile.json": MODULE.file_sha256(protected),
        }
    }

    protected.write_text('{"required_report_label": "changed"}', encoding="utf-8")
    errors = []
    MODULE.verify_project_integrity(context, tmp_path, errors)

    assert errors == ["protected project file changed during task: evaluations/profile.json"]


def test_sparse_last_page_produces_layout_warning(tmp_path: Path) -> None:
    pages = []
    for index, size in enumerate((1000, 5000, 5200, 5100, 900), start=1):
        page = tmp_path / f"page-{index:02d}.png"
        page.write_bytes(b"x" * size)
        pages.append(page)

    warnings = MODULE.page_layout_warnings(pages)

    assert warnings
    assert "last rendered page is unusually sparse" in warnings[0]


def test_normal_last_page_has_no_layout_warning(tmp_path: Path) -> None:
    pages = []
    for index, size in enumerate((1000, 5000, 5200, 5100, 4800), start=1):
        page = tmp_path / f"page-{index:02d}.png"
        page.write_bytes(b"x" * size)
        pages.append(page)

    assert MODULE.page_layout_warnings(pages) == []


def test_declared_summary_status_is_not_confused_with_structural_ok() -> None:
    assert MODULE.declared_summary_status("## 总体状态：PARTIAL") == "PARTIAL"
    assert MODULE.declared_summary_status("## 总体状态：**PASS**") == "PASS"
    assert MODULE.declared_summary_status("no status") == "UNDECLARED"
