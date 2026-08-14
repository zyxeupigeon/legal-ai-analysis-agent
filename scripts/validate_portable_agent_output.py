import argparse
import hashlib
import json
import re
import statistics
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from execution_trace_lib import trace_sha256, validate_trace


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
HTTP_URL = re.compile(r"^https?://", re.I)
CLAIM_TYPES = {"verified_fact", "company_claim", "analysis", "unverified"}
PRIMARY_SOURCE_CATEGORIES = {
    "current_model_version",
    "current_product_version",
    "pricing",
    "operator",
    "policy_status",
}

def fail(errors, message):
    errors.append(message)


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docx_text(path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt DOCX member: {bad}")
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    return "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def tables_without_repeating_headers(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    missing = []
    for index, table in enumerate(root.findall(f".//{{{WORD_NS}}}tbl"), start=1):
        first_row = table.find(f"{{{WORD_NS}}}tr")
        row_properties = first_row.find(f"{{{WORD_NS}}}trPr") if first_row is not None else None
        if row_properties is None or row_properties.find(f"{{{WORD_NS}}}tblHeader") is None:
            missing.append(index)
    return missing


def validate_claim_evidence(path, source_urls, errors):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        fail(errors, f"claim_evidence.json is unreadable or invalid: {exc}")
        return 0
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
        fail(errors, "claim evidence schema_version must be 1.0")
        return 0
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        fail(errors, "claim evidence must contain at least one claim")
        return 0

    claim_ids = set()
    analysis_dependencies = []
    normalized_sources = {url.rstrip(".,;，。；") for url in source_urls}
    for index, claim in enumerate(claims):
        label = f"claims[{index}]"
        if not isinstance(claim, dict):
            fail(errors, f"{label} must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id.strip():
            fail(errors, f"{label}.claim_id is required")
        elif claim_id in claim_ids:
            fail(errors, f"duplicate claim id: {claim_id}")
        else:
            claim_ids.add(claim_id)
        for key in ("claim_text", "category", "report_location"):
            if not isinstance(claim.get(key), str) or not claim[key].strip():
                fail(errors, f"{label}.{key} is required")
        claim_type = claim.get("claim_type")
        if claim_type not in CLAIM_TYPES:
            fail(errors, f"{label}.claim_type must be one of {sorted(CLAIM_TYPES)}")
        included = claim.get("included_in_report")
        if not isinstance(included, bool):
            fail(errors, f"{label}.included_in_report must be boolean")
        if included and claim_type == "unverified":
            fail(errors, f"{label} is unverified and cannot be included in report")

        source_url = claim.get("source_url")
        if claim_type in {"verified_fact", "company_claim"}:
            if not isinstance(source_url, str) or not HTTP_URL.match(source_url):
                fail(errors, f"{label}.source_url must be HTTP(S) for sourced claims")
            elif source_url.rstrip(".,;，。；") not in normalized_sources:
                fail(errors, f"{label}.source_url is absent from sources.md")
            if claim.get("source_tier") not in {"A", "B", "C", "M"}:
                fail(errors, f"{label}.source_tier must be A, B, C, or M")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(claim.get("accessed_at", ""))):
                fail(errors, f"{label}.accessed_at must use YYYY-MM-DD")

        if included and claim.get("category") in PRIMARY_SOURCE_CATEGORIES:
            if claim_type != "verified_fact" or claim.get("source_tier") != "A":
                fail(errors, f"{label} requires a primary official source before report inclusion")

        if claim_type == "analysis":
            dependencies = claim.get("based_on_claim_ids")
            if not isinstance(dependencies, list) or not dependencies:
                fail(errors, f"{label}.based_on_claim_ids is required for analysis")
            else:
                analysis_dependencies.append((label, dependencies))

    for label, dependencies in analysis_dependencies:
        for dependency in dependencies:
            if dependency not in claim_ids:
                fail(errors, f"{label} references unknown claim id: {dependency}")
    return len(claims)


def required_context_path(context, key):
    value = context.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"task context field is missing: {key}")
    return Path(value).resolve()


def verify_project_integrity(context, project_root, errors):
    protected_hashes = context.get("protected_project_hashes")
    if not isinstance(protected_hashes, dict) or not protected_hashes:
        fail(errors, "task context has no protected project file snapshot")
        return
    for relative_path, expected_hash in protected_hashes.items():
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            fail(errors, "task context protected project file snapshot is invalid")
            continue
        path = (project_root / relative_path).resolve()
        if not path.is_relative_to(project_root):
            fail(errors, f"protected project path escaped project root: {relative_path}")
        elif not path.is_file():
            fail(errors, f"protected project file was deleted during task: {relative_path}")
        elif file_sha256(path) != expected_hash:
            fail(errors, f"protected project file changed during task: {relative_path}")


def page_layout_warnings(pages):
    if len(pages) < 4:
        return []
    comparison_sizes = [page.stat().st_size for page in pages[1:-1]]
    median_size = statistics.median(comparison_sizes)
    last_size = pages[-1].stat().st_size
    if median_size and last_size < median_size * 0.55:
        return [
            "last rendered page is unusually sparse; inspect table continuation, page breaks, and trailing whitespace"
        ]
    return []


def declared_summary_status(summary_text):
    match = re.search(r"(?:总体状态|最终状态)\s*[：:]\s*\*{0,2}(PASS|PARTIAL|FAIL)", summary_text, re.I)
    return match.group(1).upper() if match else "UNDECLARED"


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

    errors = []
    warnings = []
    context = {}
    context_path = output_dir / "task_context.json"
    if context_path.is_file():
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            fail(errors, f"task_context.json is unreadable or invalid: {exc}")

    profile = {}
    if args.profile:
        profile_path = args.profile.resolve()
        try:
            if profile_path.is_relative_to(project_root):
                relative_profile = profile_path.relative_to(project_root).as_posix()
                protected_hashes = context.get("protected_project_hashes", {})
                expected_hash = protected_hashes.get(relative_profile)
                if not expected_hash:
                    fail(errors, f"project profile was not snapshotted at task start: {relative_profile}")
                elif not profile_path.is_file() or file_sha256(profile_path) != expected_hash:
                    fail(errors, f"project profile changed during task: {relative_profile}")
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            fail(errors, f"profile is unreadable or invalid: {exc}")

    required = [
        output_dir / "task_context.json",
        output_dir / "execution_trace.json",
        output_dir / "report.docx",
        output_dir / "sources.md",
        output_dir / "claim_evidence.json",
        output_dir / "run_summary.md",
        output_dir / "capability_declaration.md",
        output_dir / "process_optimization_report.md",
        output_dir / "render" / "report.pdf",
    ]
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            fail(errors, f"missing or empty: {path.name}")

    if context:
        try:
            if context.get("protocol_id") != "portable-agent-0.8":
                fail(errors, "task context protocol id is not portable-agent-0.8")
            if context.get("session_gate") != "READY":
                fail(errors, "task context session gate is not READY")
            if required_context_path(context, "project_root") != project_root:
                fail(errors, "task context project root does not match this project")
            if required_context_path(context, "output_root") != output_root:
                fail(errors, "task context output root does not match this project")
            if required_context_path(context, "task_output_dir") != output_dir:
                fail(errors, "task context task output directory does not match validated directory")
            verify_project_integrity(context, project_root, errors)
        except (OSError, TypeError, ValueError) as exc:
            fail(errors, f"task_context.json is unreadable or invalid: {exc}")

    pages = sorted((output_dir / "render").glob("page-*.png"))
    trace_path = output_dir / "execution_trace.json"
    trace_digest = None
    if trace_path.is_file():
        try:
            trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
            for trace_error in validate_trace(
                trace_payload,
                expected_task_id=output_dir.name,
                require_finalized=True,
                require_report_stages=True,
            ):
                fail(errors, trace_error)
            trace_digest = trace_sha256(trace_path)
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            fail(errors, f"execution_trace.json is unreadable or invalid: {exc}")

    if not pages:
        fail(errors, "no rendered page PNG files")
    else:
        warnings.extend(page_layout_warnings(pages))

    report_text = ""
    report_path = output_dir / "report.docx"
    if report_path.is_file():
        try:
            report_text = docx_text(report_path)
            missing_headers = tables_without_repeating_headers(report_path)
            if missing_headers:
                fail(
                    errors,
                    "DOCX table header row is not marked to repeat for table(s): "
                    + ", ".join(str(index) for index in missing_headers),
                )
        except Exception as exc:
            fail(errors, f"DOCX validation failed: {exc}")

    if profile.get("required_report_label") and profile["required_report_label"] not in report_text:
        fail(errors, "required report label is absent")

    sources_path = output_dir / "sources.md"
    sources_text = sources_path.read_text(encoding="utf-8") if sources_path.is_file() else ""
    source_urls = re.findall(r"https?://[^\s|)>]+", sources_text)
    if len(set(source_urls)) < int(profile.get("minimum_source_urls", 1)):
        fail(errors, "source URL count is below profile minimum")

    claim_count = 0
    claim_evidence_path = output_dir / "claim_evidence.json"
    if claim_evidence_path.is_file():
        claim_count = validate_claim_evidence(claim_evidence_path, source_urls, errors)

    evidence_text = sources_text + "\n" + report_text
    for domain in profile.get("required_source_domains", []):
        if domain.lower() not in evidence_text.lower():
            fail(errors, f"required source domain absent: {domain}")
    for pattern in profile.get("required_evidence_patterns", []):
        if not re.search(pattern, evidence_text, flags=re.IGNORECASE):
            fail(errors, f"required evidence pattern absent: {pattern}")
    for pattern in profile.get("forbidden_report_patterns", []):
        if re.search(pattern, report_text, flags=re.IGNORECASE):
            fail(errors, f"forbidden report pattern present: {pattern}")

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

        if trace_digest:
            digest_match = re.search(
                r"执行轨迹SHA-256：([0-9a-f]{64})", optimization_text, flags=re.IGNORECASE
            )
            if not digest_match or digest_match.group(1).lower() != trace_digest:
                fail(errors, "process optimization report is not bound to the finalized execution trace")
            if optimization_path.stat().st_mtime < trace_path.stat().st_mtime:
                fail(errors, "process optimization report predates the finalized execution trace")
    summary_path = output_dir / "run_summary.md"
    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
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

    for warning in warnings:
        print(f"PORTABLE_AGENT_OUTPUT_WARNING - {warning}")
    status = declared_summary_status(summary_text)
    print(
        f"PORTABLE_AGENT_OUTPUT_OK pages={len(pages)} unique_urls={len(set(source_urls))} "
        f"claims={claim_count} declared_status={status}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
