"""Build a process optimization report from a finalized execution trace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from execution_trace_lib import ensure_safe_text, trace_sha256, validate_trace, verify_task_binding


STAGE_LABELS = {
    "workspace_allocation": "任务目录分配",
    "target_scoping": "对象识别与研究范围",
    "research": "公开检索与正文读取",
    "evidence_analysis": "证据整理与分析",
    "report_generation": "Word生成",
    "rendering": "PDF与逐页图片渲染",
    "visual_qa": "逐页视觉质检",
    "remediation": "修复与复验",
    "other": "其他",
}


def cell(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def bullets(items: list[dict], formatter) -> list[str]:
    if not items:
        return ["- 未记录到此类事项。"]
    return [f"- {formatter(item)}" for item in items]


def build_report(trace_path: Path, args: argparse.Namespace) -> str:
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    errors = validate_trace(
        trace,
        expected_task_id=trace_path.parent.name,
        require_finalized=True,
        require_report_stages=True,
    )
    if errors:
        raise ValueError("invalid finalized execution trace: " + "; ".join(errors))
    subject = ensure_safe_text(args.subject, "subject")
    agent = ensure_safe_text(args.agent, "agent")
    model = ensure_safe_text(args.model, "model")
    report_file = ensure_safe_text(args.report_file, "report-file")
    if Path(report_file).name != report_file:
        raise ValueError("report-file must be a filename, not a path")

    digest = trace_sha256(trace_path)
    events = trace["events"]
    observations = trace["observations"]
    failures = [event for event in events if event["status"] in {"failed", "blocked"}]
    bottlenecks = [item for item in observations if item["kind"] in {"failure", "bottleneck"}]
    ineffective = [item for item in observations if item["kind"] == "ineffective_step"]
    risks = [item for item in observations if item["kind"] == "quality_risk"]
    reusable = [item for item in observations if item["kind"] == "reusable_practice"]
    recommendations = sorted(
        [item for item in observations if item["kind"] == "optimization_recommendation"],
        key=lambda item: (item["priority"], item["sequence"]),
    )

    lines = [
        "# 报告生成过程优化报告",
        "",
        "> 本报告由已封存的 execution_trace.json 自动生成事实骨架，只复盘本次真实执行。",
        "",
        f"- 执行轨迹SHA-256：{digest}",
        "",
        "## 1. 任务与结果概况",
        "",
        f"- 任务ID：{cell(trace['task_id'])}",
        f"- 分析对象：{cell(subject)}",
        f"- 执行日期（UTC）：{cell(trace['created_at'][:10])}",
        f"- 使用的Agent：{cell(agent)}",
        f"- 使用的模型（若可知）：{cell(model)}",
        f"- 正式报告文件名：{cell(report_file)}",
        f"- 最终状态：{cell(args.status)}",
        "",
        "## 2. 阶段记录与耗时",
        "",
        "| 阶段 | 开始时间（UTC） | 结束时间（UTC） | 耗时（秒） | 实际动作与工具 | 产出 | 状态/重试 |",
        "|---|---|---|---:|---|---|---|",
    ]
    for event in events:
        retry = f"；重试 {event['retry_of']}" if event.get("retry_of") else ""
        action = f"{event['action']}（{event['tool']}）"
        lines.append(
            "| "
            + " | ".join([
                cell(STAGE_LABELS[event["stage"]]),
                cell(event["started_at"]),
                cell(event["ended_at"]),
                cell(event["duration_seconds"]),
                cell(action),
                cell("、".join(event["artifacts"])),
                cell(event["status"] + retry),
            ])
            + " |"
        )

    lines.extend(["", "## 3. 本次失败、重试与瓶颈", ""])
    lines.extend(bullets(
        failures,
        lambda item: (
            f"事件 {item['event_id']}（{STAGE_LABELS[item['stage']]}）状态为 {item['status']}："
            f"{item.get('note') or item['action']}"
        ),
    ))
    lines.extend(bullets(
        bottlenecks,
        lambda item: (
            f"{item['summary']}；影响：{item['impact']}；处理：{item.get('resolution') or '尚未记录'}"
        ),
    ))

    lines.extend(["", "## 4. 无效或重复步骤", ""])
    lines.extend(bullets(
        ineffective,
        lambda item: (
            f"{item['summary']}；影响：{item['impact']}；下次处理：{item.get('resolution') or '尚未记录'}"
        ),
    ))

    lines.extend(["", "## 5. 质量风险与人工验收重点", ""])
    lines.extend(bullets(
        risks,
        lambda item: (
            f"{item['summary']}；影响：{item['impact']}；当前处置：{item.get('resolution') or '尚未记录'}"
        ),
    ))

    lines.extend(["", "## 6. 可复用做法", ""])
    lines.extend(bullets(
        reusable,
        lambda item: f"{item['summary']}；已验证收益：{item['impact']}",
    ))

    lines.extend([
        "",
        "## 7. 下一轮优化建议",
        "",
        "| 优先级 | 建议 | 预期收益 | 实现成本 | 风险/副作用 | 建议验证方法 |",
        "|---|---|---|---|---|---|",
    ])
    for item in recommendations:
        lines.append(
            "| "
            + " | ".join(cell(value) for value in (
                item["priority"],
                item["summary"],
                item["expected_benefit"],
                item["implementation_cost"],
                item["risk"],
                item["validation_method"],
            ))
            + " |"
        )
    lines.extend([
        "",
        "以上建议仅来自本次执行轨迹中的已记录观察，并按优先级排序；未记录的信息不作推断。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--agent", default="未记录")
    parser.add_argument("--model", default="未记录")
    parser.add_argument("--status", required=True, choices=("PASS", "PARTIAL", "FAIL"))
    parser.add_argument("--report-file", default="report.docx")
    args = parser.parse_args()
    task_dir = args.task_dir.resolve()
    trace_path = task_dir / "execution_trace.json"
    output_path = task_dir / "process_optimization_report.md"
    try:
        verify_task_binding(task_dir, Path(__file__).resolve().parents[1])
        report = build_report(trace_path, args)
        output_path.write_text(report, encoding="utf-8", newline="\n")
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        print("PROCESS_OPTIMIZATION_REPORT_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc
    print("PROCESS_OPTIMIZATION_REPORT_OK")
    print(f"OUTPUT={output_path}")


if __name__ == "__main__":
    main()
