import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate_open_source_discovery.py"
SPEC = importlib.util.spec_from_file_location("validate_open_source_discovery", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source(name="github", status="success"):
    return {
        "name": name,
        "type": "repository_search",
        "status": status,
        "evidence_url": "https://github.com/search",
    }


def exact_candidate():
    return {
        "repository": "ossf/scorecard",
        "url": "https://github.com/ossf/scorecard",
        "functional_fit": "exact",
        "recommendation": "replace_candidate",
        "evidence_urls": [
            "https://github.com/ossf/scorecard",
            "https://api.scorecard.dev/projects/github.com/ossf/scorecard",
        ],
        "license": {"spdx": "Apache-2.0", "status": "compatible"},
        "maturity": {
            "archived": False,
            "last_activity_at": "2026-08-10",
            "adoption_evidence": ["used by established open-source projects"],
        },
        "validation": {"status": "passed", "method": "public API request"},
        "covered_capabilities": ["repository risk enrichment"],
        "gaps": [],
        "risks": ["heuristic scores require interpretation"],
    }


def near_candidate():
    candidate = exact_candidate()
    candidate.update(
        {
            "repository": "chaoss/grimoirelab",
            "url": "https://github.com/chaoss/grimoirelab",
            "functional_fit": "near",
            "recommendation": "user_review_only",
            "evidence_urls": ["https://github.com/chaoss/grimoirelab"],
            "covered_capabilities": ["repository activity analytics"],
            "gaps": ["does not generate candidates"],
            "risks": ["heavy local deployment"],
        }
    )
    candidate["validation"] = {"status": "not_run", "method": "documentation review"}
    return candidate


def payload(decision, candidates, sources=None, chosen=None):
    value = {
        "protocol_version": "open-source-discovery-0.1",
        "task": "find a mature repository risk evaluator",
        "generated_at": "2026-08-11T06:00:00Z",
        "sources": sources if sources is not None else [source()],
        "candidates": candidates,
        "decision": decision,
    }
    if chosen is not None:
        value["chosen_repository"] = chosen
    return value


class OpenSourceDiscoveryValidationTests(unittest.TestCase):
    def test_exact_candidate_passes(self):
        value = payload(
            "exact_candidate_found",
            [exact_candidate()],
            chosen="ossf/scorecard",
        )
        self.assertEqual(MODULE.validate_payload(value), [])

    def test_near_candidate_is_user_review_only(self):
        value = payload("near_candidates_only", [near_candidate()])
        self.assertEqual(MODULE.validate_payload(value), [])

    def test_near_candidate_cannot_be_auto_replaced(self):
        candidate = near_candidate()
        candidate["recommendation"] = "replace_candidate"
        value = payload(
            "exact_candidate_found",
            [candidate],
            chosen="chaoss/grimoirelab",
        )
        errors = MODULE.validate_payload(value)
        self.assertTrue(any("near fit must be user_review_only" in item for item in errors))
        self.assertTrue(any("replace_candidate requires exact fit" in item for item in errors))

    def test_blocked_optional_source_can_fall_back(self):
        sources = [
            source("ecosyste-ms-awesome", "blocked"),
            source("github", "success"),
        ]
        value = payload("near_candidates_only", [near_candidate()], sources=sources)
        self.assertEqual(MODULE.validate_payload(value), [])

    def test_all_sources_blocked_requires_blocked_decision(self):
        sources = [
            source("ecosyste-ms-awesome", "blocked"),
            source("github", "failed"),
        ]
        value = payload("discovery_blocked", [], sources=sources)
        self.assertEqual(MODULE.validate_payload(value), [])

    def test_blocked_decision_rejects_successful_source(self):
        value = payload("discovery_blocked", [], sources=[source("github", "success")])
        errors = MODULE.validate_payload(value)
        self.assertTrue(any("all sources" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
