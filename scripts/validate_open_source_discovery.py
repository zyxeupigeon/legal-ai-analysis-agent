import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

PROTOCOL_VERSION = "open-source-discovery-0.1"
DECISIONS = {
    "exact_candidate_found",
    "near_candidates_only",
    "no_suitable_candidate",
    "discovery_blocked",
}
SOURCE_STATUSES = {"success", "blocked", "failed"}
FUNCTIONAL_FITS = {"exact", "near", "none"}
RECOMMENDATIONS = {"replace_candidate", "user_review_only", "reject"}


def is_http_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def require_mapping(value, label, errors):
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def require_nonempty_list(value, label, errors):
    if not isinstance(value, list) or not value:
        errors.append(f"{label} must be a non-empty list")
        return []
    return value


def validate_payload(payload):
    errors = []
    payload = require_mapping(payload, "root", errors)

    if payload.get("protocol_version") != PROTOCOL_VERSION:
        errors.append(f"protocol_version must be {PROTOCOL_VERSION}")
    if not isinstance(payload.get("task"), str) or not payload["task"].strip():
        errors.append("task must be a non-empty string")
    if not isinstance(payload.get("generated_at"), str) or not payload["generated_at"].strip():
        errors.append("generated_at must be a non-empty string")

    sources = require_nonempty_list(payload.get("sources"), "sources", errors)
    successful_sources = 0
    for index, source_value in enumerate(sources):
        source = require_mapping(source_value, f"sources[{index}]", errors)
        if not isinstance(source.get("name"), str) or not source["name"].strip():
            errors.append(f"sources[{index}].name must be non-empty")
        if not isinstance(source.get("type"), str) or not source["type"].strip():
            errors.append(f"sources[{index}].type must be non-empty")
        status = source.get("status")
        if status not in SOURCE_STATUSES:
            errors.append(f"sources[{index}].status is invalid")
        if status == "success":
            successful_sources += 1
        evidence_url = source.get("evidence_url")
        if evidence_url is not None and not is_http_url(evidence_url):
            errors.append(f"sources[{index}].evidence_url must be HTTP(S)")

    candidates_value = payload.get("candidates")
    if not isinstance(candidates_value, list):
        errors.append("candidates must be a list")
        candidates = []
    else:
        candidates = candidates_value

    replace_candidates = []
    near_candidates = []
    repositories = set()

    for index, candidate_value in enumerate(candidates):
        label = f"candidates[{index}]"
        candidate = require_mapping(candidate_value, label, errors)
        repository = candidate.get("repository")
        if not isinstance(repository, str) or "/" not in repository:
            errors.append(f"{label}.repository must use owner/name")
        else:
            repositories.add(repository)

        if not is_http_url(candidate.get("url")):
            errors.append(f"{label}.url must be HTTP(S)")

        fit = candidate.get("functional_fit")
        recommendation = candidate.get("recommendation")
        if fit not in FUNCTIONAL_FITS:
            errors.append(f"{label}.functional_fit is invalid")
        if recommendation not in RECOMMENDATIONS:
            errors.append(f"{label}.recommendation is invalid")

        evidence_urls = require_nonempty_list(
            candidate.get("evidence_urls"), f"{label}.evidence_urls", errors
        )
        for evidence_index, url in enumerate(evidence_urls):
            if not is_http_url(url):
                errors.append(
                    f"{label}.evidence_urls[{evidence_index}] must be HTTP(S)"
                )

        license_info = require_mapping(candidate.get("license"), f"{label}.license", errors)
        maturity = require_mapping(candidate.get("maturity"), f"{label}.maturity", errors)
        validation = require_mapping(
            candidate.get("validation"), f"{label}.validation", errors
        )

        if fit == "near":
            near_candidates.append(repository)
            if recommendation != "user_review_only":
                errors.append(f"{label}: near fit must be user_review_only")
            for field in ("covered_capabilities", "gaps", "risks"):
                require_nonempty_list(candidate.get(field), f"{label}.{field}", errors)

        if fit == "none" and recommendation != "reject":
            errors.append(f"{label}: none fit must be reject")

        if recommendation == "replace_candidate":
            replace_candidates.append(repository)
            if fit != "exact":
                errors.append(f"{label}: replace_candidate requires exact fit")
            if validation.get("status") != "passed":
                errors.append(f"{label}: replace_candidate requires passed validation")
            if license_info.get("status") != "compatible":
                errors.append(f"{label}: replace_candidate requires compatible license")
            if maturity.get("archived") is not False:
                errors.append(f"{label}: replace_candidate requires archived=false")
            require_nonempty_list(
                maturity.get("adoption_evidence"),
                f"{label}.maturity.adoption_evidence",
                errors,
            )

    decision = payload.get("decision")
    if decision not in DECISIONS:
        errors.append("decision is invalid")
    chosen = payload.get("chosen_repository")

    if decision == "exact_candidate_found":
        if not replace_candidates:
            errors.append("exact_candidate_found requires a replace_candidate")
        if chosen not in replace_candidates:
            errors.append("chosen_repository must identify a replace_candidate")
    else:
        if chosen not in (None, ""):
            errors.append("chosen_repository is allowed only for exact_candidate_found")

    if decision == "near_candidates_only":
        if replace_candidates:
            errors.append("near_candidates_only cannot contain replace_candidate")
        if not near_candidates:
            errors.append("near_candidates_only requires at least one near candidate")

    if decision == "no_suitable_candidate":
        if replace_candidates or near_candidates:
            errors.append("no_suitable_candidate cannot contain exact replacement or near fit")

    if decision == "discovery_blocked":
        if successful_sources:
            errors.append("discovery_blocked requires all sources to be blocked or failed")
        if replace_candidates:
            errors.append("discovery_blocked cannot contain replace_candidate")
    elif not successful_sources:
        errors.append("a non-blocked decision requires at least one successful source")

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_file", type=Path)
    args = parser.parse_args()

    try:
        payload = json.loads(args.result_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print("OPEN_SOURCE_DISCOVERY_FAIL")
        print(f"- cannot read result JSON: {exc}")
        return 1

    errors = validate_payload(payload)
    if errors:
        print("OPEN_SOURCE_DISCOVERY_FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "OPEN_SOURCE_DISCOVERY_OK "
        f"candidates={len(payload['candidates'])} decision={payload['decision']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
