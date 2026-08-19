import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_every_agent_entry_requires_first_message_preflight_and_delivery_paths() -> None:
    for relative_path in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "first user message of every new session" in text
        assert "Start the first reply with SESSION_PREFLIGHT_READY or SESSION_PREFLIGHT_BLOCKED" in text
        assert "process_optimization_report.md" in text
        assert "execution_trace.json" in text
        assert "finalized trace" in text
        assert "report_diff.json" in text
        assert "report_manifest.json" in text
        assert "absolute path and filename" in text


def test_protocol_defines_optimization_report_contract() -> None:
    protocol = (REPO_ROOT / "PROJECT_AGENT_PROTOCOL.md").read_text(encoding="utf-8")
    template = (REPO_ROOT / "docs" / "PROCESS_OPTIMIZATION_REPORT_TEMPLATE.md").read_text(
        encoding="utf-8"
    )

    assert "协议编号：portable-agent-1.1" in protocol
    assert "新会话的第一项动作必须是项目预检" in protocol
    assert "SESSION_PREFLIGHT_READY" in protocol
    assert "SESSION_PREFLIGHT_BLOCKED" in protocol
    assert "session_preflight_gate.py prepare" in protocol
    assert "CAPABILITY_RECEIPT" in protocol
    assert "scripts/render_report.py" in protocol
    assert "unmanifested formal duplicates" in protocol
    assert "不得运行任务目录分配器" in protocol
    assert "不得生成正式 Word" in protocol
    assert "process_optimization_report.md" in protocol
    assert "execution_trace.json" in protocol
    assert "docs/EXECUTION_TRACE_SCHEMA.md" in protocol
    assert "scripts/record_execution_event.py finalize" in protocol
    assert "scripts/build_process_optimization_report.py" in protocol
    assert "scripts/compare_report_versions.py" in protocol
    assert "scripts/build_report_manifest.py" in protocol
    assert "docs/REPORT_VERSIONING.md" in protocol
    assert "文件名和绝对路径" in protocol
    for section in (
        "任务与结果概况",
        "阶段记录与耗时",
        "本次失败、重试与瓶颈",
        "无效或重复步骤",
        "质量风险与人工验收重点",
        "可复用做法",
        "下一轮优化建议",
    ):
        assert section in template


def test_validator_requires_process_optimization_report() -> None:
    output_root = REPO_ROOT / "agent_outputs"
    output_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="optimization-contract-", dir=output_root) as directory:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate_portable_agent_output.py"),
                directory,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert result.returncode == 1
    assert "missing or empty: process_optimization_report.md" in result.stdout
    assert "missing or empty: execution_trace.json" in result.stdout
    assert "missing or empty: report_diff.json" in result.stdout
    assert "missing or empty: report_manifest.json" in result.stdout
