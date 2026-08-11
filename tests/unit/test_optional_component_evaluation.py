import argparse
import asyncio

import pytest

from scripts import evaluate_optional_components as evaluation


def test_output_directory_must_stay_inside_agent_outputs():
    accepted = evaluation.safe_output_dir("agent_outputs/component-test")
    assert accepted.is_relative_to(evaluation.OUTPUT_ROOT.resolve())

    with pytest.raises(argparse.ArgumentTypeError):
        evaluation.safe_output_dir("tmp/component-test")


def test_markitdown_absence_is_reported_without_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation, "package_version", lambda _name: None)

    result = evaluation.evaluate_markitdown(None, tmp_path)

    assert result == {
        "component": "markitdown",
        "version": None,
        "status": "not_installed",
    }


def test_crawl4ai_absence_is_reported_without_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation, "package_version", lambda _name: None)

    result = asyncio.run(evaluation.evaluate_crawl4ai(None, None, tmp_path))

    assert result == {
        "component": "crawl4ai",
        "version": None,
        "status": "not_installed",
    }
