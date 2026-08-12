import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def fail(errors, message):
    errors.append(message)


def docx_text(path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt DOCX member: {bad}")
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    return "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def required_context_path(context, key):
    value = context.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"task context field is missing: {key}")
    return Path(value).resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    project_root = Path(__file__).resolve().parents[1]
    output_root = (project_root / "agent_outputs").resolve()
    if not output_dir.is_relative_to(output_root):
        print("PORTABLE_AGENT_OUTPUT_FAIL")
        print(f"- output directory is outside this project agent_outputs: {output_dir}")
        return 1

    profile = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else {}
    errors = []

    required = [
        output_dir / "task_context.json",
        output_dir / "report.docx",
        output_dir / "sources.md",
        output_dir / "run_summary.md",
        output_dir / "capability_declaration.md",
        output_dir / "process_optimization_report.md",
        output_dir / "render" / "report.pdf",
    ]
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            fail(errors, f"missing or empty: {path.name}")

    context_path = output_dir / "task_context.json"
    if context_path.is_file():
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
            if context.get("protocol_id") != "portable-agent-0.4":
                fail(errors, "task context protocol id is not portable-agent-0.4")
            if required_context_path(context, "project_root") != project_root:
                fail(errors, "task context project root does not match this project")
            if required_context_path(context, "output_root") != output_root:
                fail(errors, "task context output root does not match this project")
            if required_context_path(context, "task_output_dir") != output_dir:
                fail(errors, "task context task output directory does not match validated directory")
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            fail(errors, f"task_context.json is unreadable or invalid: {exc}")

    pages = sorted((output_dir / "render").glob("page-*.png"))
    if not pages:
        fail(errors, "no rendered page PNG files")

    report_text = ""
    report_path = output_dir / "report.docx"
    if report_path.is_file():
        try:
            report_text = docx_text(report_path)
        except Exception as exc:
            fail(errors, f"DOCX validation failed: {exc}")

    if profile.get("required_report_label") and profile["required_report_label"] not in report_text:
        fail(errors, "required report label is absent")

    sources_path = output_dir / "sources.md"
    sources_text = sources_path.read_text(encoding="utf-8") if sources_path.is_file() else ""
    source_urls = re.findall(r"https?://[^\s|)>]+", sources_text)
    if len(set(source_urls)) < int(profile.get("minimum_source_urls", 1)):
        fail(errors, "source URL count is below profile minimum")

    evidence_text = sources_text + "\n" + report_text
    for domain in profile.get("required_source_domains", []):
        if domain.lower() not in evidence_text.lower():
            fail(errors, f"required source domain absent: {domain}")
    for pattern in profile.get("required_evidence_patterns", []):
        if not re.search(pattern, evidence_text, flags=re.IGNORECASE):
            fail(errors, f"required evidence pattern absent: {pattern}")

    optimization_path = output_dir / "process_optimization_report.md"
    if optimization_path.is_file():
        optimization_text = optimization_path.read_text(encoding="utf-8")
        required_sections = [
            "任务与结果概况",
            "阶段记录与耗时",
            "本次失败、重试与瓶颈",
            "无效或重复步骤",
            "质量风险与人工验收重点",
            "可复用做法",
            "下一轮优化建议",
        ]
        if len(optimization_text.strip()) < 300:
            fail(errors, "process optimization report is too short")
        for section in required_sections:
            if section not in optimization_text:
                fail(errors, f"process optimization report section absent: {section}")

    summary_path = output_dir / "run_summary.md"
    if summary_path.is_file() and report_path.is_file() and pages and optimization_path.is_file():
        newest_artifact = max(
            [
                report_path.stat().st_mtime,
                optimization_path.stat().st_mtime,
                *(p.stat().st_mtime for p in pages),
            ]
        )
        if summary_path.stat().st_mtime < newest_artifact:
            fail(errors, "run_summary predates final report, rendered pages, or optimization report")

    if errors:
        print("PORTABLE_AGENT_OUTPUT_FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"PORTABLE_AGENT_OUTPUT_OK pages={len(pages)} unique_urls={len(set(source_urls))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
