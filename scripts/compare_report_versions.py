"""Compare a completed report with the latest verified report for the same subject."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from execution_trace_lib import validate_trace
from report_version_lib import (
    DIFF_SCHEMA_VERSION,
    DYNAMIC_CATEGORIES,
    PROTOCOL_ID,
    atomic_write_json,
    extract_source_urls,
    file_sha256,
    load_claims,
    load_json,
    parse_timestamp,
    safe_subject,
    subject_key,
    trace_metrics,
    utc_now,
    validate_manifest,
    verify_task_directory,
)


def changed_fields(before: dict, after: dict) -> list[str]:
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def compare_claim_sets(before: dict[str, dict], after: dict[str, dict]) -> dict:
    before_ids = set(before)
    after_ids = set(after)
    changed = []
    for claim_id in sorted(before_ids & after_ids):
        fields = changed_fields(before[claim_id], after[claim_id])
        if fields:
            changed.append({
                "claim_id": claim_id,
                "changed_fields": fields,
                "before": before[claim_id],
                "after": after[claim_id],
            })
    return {
        "added": [after[claim_id] for claim_id in sorted(after_ids - before_ids)],
        "removed": [before[claim_id] for claim_id in sorted(before_ids - after_ids)],
        "changed": changed,
    }


def select_claims(claims: dict[str, dict], predicate) -> dict[str, dict]:
    return {claim_id: claim for claim_id, claim in claims.items() if predicate(claim)}


def blank_comparison(current: dict[str, dict]) -> dict:
    return {"added": [current[key] for key in sorted(current)], "removed": [], "changed": []}


def efficiency_comparison(current: dict, baseline: dict | None) -> dict:
    if baseline is None:
        return {"current": current, "baseline": None, "stage_deltas": {}}
    stages = sorted(set(current["stages"]) | set(baseline["stages"]))
    stage_deltas = {}
    for stage in stages:
        current_stage = current["stages"].get(
            stage, {"duration_seconds": 0.0, "attempts": 0, "failures": 0, "retries": 0}
        )
        baseline_stage = baseline["stages"].get(
            stage, {"duration_seconds": 0.0, "attempts": 0, "failures": 0, "retries": 0}
        )
        stage_deltas[stage] = {
            key: round(float(current_stage[key]) - float(baseline_stage[key]), 3)
            for key in ("duration_seconds", "attempts", "failures", "retries")
        }
    return {"current": current, "baseline": baseline, "stage_deltas": stage_deltas}


def find_baseline(task_dir: Path, key: str) -> tuple[Path | None, dict | None]:
    candidates = []
    for manifest_path in task_dir.parent.glob("*/report_manifest.json"):
        candidate_dir = manifest_path.parent.resolve()
        if candidate_dir == task_dir:
            continue
        try:
            manifest = load_json(manifest_path)
            if manifest.get("subject_key") != key:
                continue
            if manifest.get("final_status") not in {"PASS", "PARTIAL"}:
                continue
            verify_task_directory(candidate_dir, task_dir.parent.parent)
            if validate_manifest(candidate_dir, manifest):
                continue
            completed = parse_timestamp(manifest.get("completed_at"))
            candidates.append((completed, candidate_dir, manifest))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    if not candidates:
        return None, None
    _, candidate_dir, manifest = max(candidates, key=lambda item: item[0])
    return candidate_dir, manifest


def render_claim_section(title: str, comparison: dict) -> list[str]:
    lines = [f"## {title}", ""]
    lines.append(
        f"新增 {len(comparison['added'])} 条；移除 {len(comparison['removed'])} 条；修改 {len(comparison['changed'])} 条。"
    )
    lines.append("")
    for label, key in (("新增", "added"), ("移除", "removed")):
        if comparison[key]:
            lines.append(f"### {label}")
            lines.append("")
            for claim in comparison[key]:
                lines.append(f"- `{claim.get('claim_id')}` {claim.get('claim_text', '')}")
            lines.append("")
    if comparison["changed"]:
        lines.extend(["### 修改", ""])
        for item in comparison["changed"]:
            lines.append(
                f"- `{item['claim_id']}` 变化字段：{', '.join(item['changed_fields'])}；"
                f"原：{item['before'].get('claim_text', '')}；现：{item['after'].get('claim_text', '')}"
            )
        lines.append("")
    if not any(comparison.values()):
        lines.extend(["无变化。", ""])
    return lines


def render_markdown(payload: dict) -> str:
    baseline = payload["baseline"]
    lines = [
        "# 报告版本差异",
        "",
        f"- 分析对象：{payload['subject']}",
        f"- 当前任务：{payload['current_task_id']}",
        f"- 对比基线：{baseline.get('task_id') or '未找到（首次纳入版本管理）'}",
        f"- 生成时间：{payload['generated_at']}",
        "",
    ]
    if baseline["status"] == "not_found":
        lines.extend([
            "> 当前项目中没有同一分析对象且清单校验通过的历史报告；本文件记录首个基线。",
            "",
        ])
    lines.extend(render_claim_section("事实与主张变化", payload["claims"]))
    lines.extend(render_claim_section("分析结论变化", payload["analysis_conclusions"]))
    lines.extend(render_claim_section("高时效事实提醒", payload["dynamic_claims"]))
    lines.extend(["## 来源变化", ""])
    lines.append(f"新增来源 {len(payload['sources']['added'])} 个；移除来源 {len(payload['sources']['removed'])} 个。")
    lines.append("")
    for label, key in (("新增", "added"), ("移除", "removed")):
        if payload["sources"][key]:
            lines.extend([f"### {label}", ""])
            lines.extend(f"- {url}" for url in payload["sources"][key])
            lines.append("")
    efficiency = payload["efficiency"]
    lines.extend(["## 流程效率变化", ""])
    if efficiency["baseline"] is None:
        lines.append(
            f"当前记录总耗时 {efficiency['current']['total_duration_seconds']:.3f} 秒；首次运行暂无历史效率基线。"
        )
    else:
        delta = (
            efficiency["current"]["total_duration_seconds"]
            - efficiency["baseline"]["total_duration_seconds"]
        )
        lines.append(
            f"当前总耗时 {efficiency['current']['total_duration_seconds']:.3f} 秒，"
            f"基线 {efficiency['baseline']['total_duration_seconds']:.3f} 秒，差值 {delta:+.3f} 秒。"
        )
        lines.extend(["", "| 阶段 | 耗时差（秒） | 尝试次数差 | 失败次数差 | 重试次数差 |", "|---|---:|---:|---:|---:|"])
        for stage, values in efficiency["stage_deltas"].items():
            lines.append(
                f"| {stage} | {values['duration_seconds']:+.3f} | {int(values['attempts']):+d} | "
                f"{int(values['failures']):+d} | {int(values['retries']):+d} |"
            )
    lines.extend(["", "## 下一次复核提醒", ""])
    lines.extend(f"- {item}" for item in payload["reminders"])
    lines.append("")
    return "\n".join(lines)


def build_diff(task_dir: Path, subject: str, project_root: Path) -> dict:
    context = verify_task_directory(task_dir, project_root)
    task_dir = task_dir.resolve()
    subject = safe_subject(subject)
    key = subject_key(subject)
    current_claims = load_claims(task_dir / "claim_evidence.json")
    current_sources = extract_source_urls(task_dir / "sources.md")
    trace = load_json(task_dir / "execution_trace.json")
    trace_errors = validate_trace(
        trace, expected_task_id=task_dir.name, require_finalized=True, require_report_stages=True
    )
    if trace_errors:
        raise ValueError("execution trace is not finalized and valid: " + "; ".join(trace_errors))
    current_metrics = trace_metrics(task_dir / "execution_trace.json")

    baseline_dir, baseline_manifest = find_baseline(task_dir, key)
    if baseline_dir is None:
        baseline_claims: dict[str, dict] = {}
        baseline_sources: list[str] = []
        baseline_metrics = None
        baseline = {
            "status": "not_found",
            "task_id": None,
            "completed_at": None,
            "manifest_sha256": None,
        }
    else:
        baseline_claims = load_claims(baseline_dir / "claim_evidence.json")
        baseline_sources = extract_source_urls(baseline_dir / "sources.md")
        baseline_metrics = trace_metrics(baseline_dir / "execution_trace.json")
        baseline = {
            "status": "found",
            "task_id": baseline_dir.name,
            "completed_at": baseline_manifest["completed_at"],
            "manifest_sha256": file_sha256(baseline_dir / "report_manifest.json"),
        }

    compare = compare_claim_sets if baseline_dir else lambda _before, after: blank_comparison(after)
    claims = compare(baseline_claims, current_claims)
    analysis = compare(
        select_claims(baseline_claims, lambda claim: claim.get("claim_type") == "analysis"),
        select_claims(current_claims, lambda claim: claim.get("claim_type") == "analysis"),
    )
    dynamic = compare(
        select_claims(baseline_claims, lambda claim: claim.get("category") in DYNAMIC_CATEGORIES),
        select_claims(current_claims, lambda claim: claim.get("category") in DYNAMIC_CATEGORIES),
    )
    sources = {
        "added": sorted(set(current_sources) - set(baseline_sources)),
        "removed": sorted(set(baseline_sources) - set(current_sources)),
    }
    reminders = []
    if baseline_dir is None:
        reminders.append("首次纳入版本管理；下次同一对象报告将以本次清单为自动对比基线。")
    if baseline_dir is not None and any(dynamic.values()):
        reminders.append("当前版本、价格、运营主体或政策状态发生变化；请逐条复核本轮一级官方来源。")
    if sources["removed"]:
        reminders.append("存在移除的来源；请确认对应事实已删除、替换或降级，而非遗漏证据。")
    if analysis["removed"] or analysis["changed"]:
        reminders.append("分析结论发生删改；请人工确认变化由新证据支持，而非表述漂移。")
    if not reminders:
        reminders.append("未检测到结构化变化；仍需人工复核正文语义、页面视觉和外部事实时效。")

    payload = {
        "schema_version": DIFF_SCHEMA_VERSION,
        "protocol_id": context["protocol_id"],
        "subject": subject,
        "subject_key": key,
        "current_task_id": task_dir.name,
        "generated_at": utc_now(),
        "baseline": baseline,
        "claims": claims,
        "analysis_conclusions": analysis,
        "dynamic_claims": dynamic,
        "sources": sources,
        "efficiency": efficiency_comparison(current_metrics, baseline_metrics),
        "reminders": reminders,
    }
    atomic_write_json(task_dir / "report_diff.json", payload)
    (task_dir / "report_diff.md").write_text(render_markdown(payload), encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--subject", required=True)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    try:
        payload = build_diff(args.task_dir, args.subject, project_root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("REPORT_DIFF_FAIL")
        print(f"- {exc}")
        raise SystemExit(1) from exc
    print("REPORT_DIFF_OK")
    print(f"BASELINE={payload['baseline'].get('task_id') or 'NONE'}")
    print(f"REPORT_DIFF_JSON={(args.task_dir.resolve() / 'report_diff.json')}")
    print(f"REPORT_DIFF_MD={(args.task_dir.resolve() / 'report_diff.md')}")


if __name__ == "__main__":
    main()
