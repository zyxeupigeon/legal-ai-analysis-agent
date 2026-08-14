import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "create_task_workspace.py"
SPEC = importlib.util.spec_from_file_location("create_task_workspace", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def configure_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    project_root = tmp_path / "project-copy"
    project_root.mkdir()
    (project_root / "PROJECT_AGENT_PROTOCOL.md").write_text("test protocol", encoding="utf-8")
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(MODULE, "OUTPUT_ROOT", project_root / "agent_outputs")
    monkeypatch.setattr(MODULE, "PROTECTED_FIXED_PATHS", ("PROJECT_AGENT_PROTOCOL.md",))
    receipt = {
        "receipt_id": "test-receipt",
        "capabilities": {
            "internet_search": "READY",
            "page_reading": "READY",
            "word_generation": "READY",
            "pdf_png_rendering": "READY",
            "direct_image_inspection": "READY",
        },
        "visual_probe_verified": True,
        "document_self_test": "READY",
    }
    monkeypatch.setattr(MODULE, "validate_capability_receipt", lambda *args, **kwargs: receipt)
    monkeypatch.setattr(MODULE, "consume_capability_receipt", lambda *args, **kwargs: receipt)
    monkeypatch.chdir(project_root)
    monkeypatch.delenv("LEGAL_AI_PROJECT_ROOT", raising=False)
    return project_root


def test_task_workspace_is_anchored_to_current_project(monkeypatch, tmp_path):
    project_root = configure_project(monkeypatch, tmp_path)

    output_dir = MODULE.allocate("delifasou_20260811", "READY", Path("test-receipt.json"))

    assert output_dir == project_root / "agent_outputs" / "delifasou_20260811"
    context = json.loads((output_dir / "task_context.json").read_text(encoding="utf-8"))
    assert Path(context["project_root"]) == project_root
    assert Path(context["task_output_dir"]) == output_dir
    assert context["protocol_id"] == "portable-agent-1.0"
    assert context["session_gate"] == "READY"
    assert context["visual_probe_verified"] is True
    assert context["session_capabilities"]["direct_image_inspection"] == "READY"
    assert set(context["protected_project_hashes"]) == {"PROJECT_AGENT_PROTOCOL.md"}
    trace = json.loads((output_dir / "execution_trace.json").read_text(encoding="utf-8"))
    assert trace["schema_version"] == "1.0"
    assert trace["task_id"] == "delifasou_20260811"
    assert trace["events"][0]["stage"] == "workspace_allocation"
    assert trace["events"][0]["status"] == "succeeded"


def test_wrong_current_directory_is_rejected(monkeypatch, tmp_path):
    project_root = configure_project(monkeypatch, tmp_path)
    wrong_directory = tmp_path / "other-copy"
    wrong_directory.mkdir()
    monkeypatch.chdir(wrong_directory)

    with pytest.raises(RuntimeError, match="current working directory"):
        MODULE.allocate("must_fail", "READY", Path("test-receipt.json"))

    assert not (project_root / "agent_outputs" / "must_fail").exists()


def test_launcher_root_mismatch_is_rejected(monkeypatch, tmp_path):
    project_root = configure_project(monkeypatch, tmp_path)
    monkeypatch.setenv("LEGAL_AI_PROJECT_ROOT", str(tmp_path / "different-project"))

    with pytest.raises(RuntimeError, match="launcher project root"):
        MODULE.allocate("must_fail", "READY", Path("test-receipt.json"))

    assert not (project_root / "agent_outputs" / "must_fail").exists()


def test_existing_task_directory_is_not_reused(monkeypatch, tmp_path):
    configure_project(monkeypatch, tmp_path)
    MODULE.allocate("unique_task", "READY", Path("test-receipt.json"))

    with pytest.raises(FileExistsError):
        MODULE.allocate("unique_task", "READY", Path("test-receipt.json"))


def test_blocked_session_cannot_create_task_workspace(monkeypatch, tmp_path):
    project_root = configure_project(monkeypatch, tmp_path)

    with pytest.raises(RuntimeError, match="session preflight is not READY"):
        MODULE.allocate("blocked_task", "BLOCKED", Path("test-receipt.json"))

    assert not (project_root / "agent_outputs" / "blocked_task").exists()
