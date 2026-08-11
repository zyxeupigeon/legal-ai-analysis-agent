"""Evaluate optional document and web extraction components in isolation.

This script does not install packages or call an application service. It records
whether optional components are available and, when a sample is supplied,
whether they can produce useful text for the portable-agent workflow.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "agent_outputs"


def package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def safe_output_dir(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    try:
        path.relative_to(OUTPUT_ROOT.resolve())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "output directory must be inside agent_outputs"
        ) from exc
    return path


def evaluate_markitdown(docx: Path | None, output_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "component": "markitdown",
        "version": package_version("markitdown"),
        "status": "not_installed",
    }
    if result["version"] is None:
        return result

    try:
        from markitdown import MarkItDown
    except Exception as exc:  # dependency/import failures are evaluation evidence
        result.update(status="import_failed", error=f"{type(exc).__name__}: {exc}")
        return result

    result["status"] = "available_not_exercised"
    if docx is None:
        return result
    if not docx.is_file():
        result.update(status="sample_missing", sample=str(docx))
        return result

    try:
        converted = MarkItDown().convert(str(docx))
        text = converted.text_content
        output_path = output_dir / "markitdown-output.md"
        output_path.write_text(text, encoding="utf-8")
        result.update(
            status="passed" if text.strip() else "empty_output",
            sample=str(docx.resolve()),
            output=str(output_path.resolve()),
            character_count=len(text),
            table_marker_count=text.count("|"),
        )
    except Exception as exc:
        result.update(status="conversion_failed", error=f"{type(exc).__name__}: {exc}")
    return result


async def evaluate_crawl4ai(
    url: str | None, expected_text: str | None, output_dir: Path
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "component": "crawl4ai",
        "version": package_version("crawl4ai"),
        "status": "not_installed",
    }
    if result["version"] is None:
        return result

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except Exception as exc:
        result.update(status="import_failed", error=f"{type(exc).__name__}: {exc}")
        return result

    result["status"] = "available_not_exercised"
    if not url:
        return result

    try:
        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
        async with AsyncWebCrawler(config=browser_config) as crawler:
            crawled = await crawler.arun(url=url, config=run_config)
        markdown_value = getattr(crawled, "markdown", "")
        text = getattr(markdown_value, "raw_markdown", None) or str(markdown_value)
        output_path = output_dir / "crawl4ai-output.md"
        output_path.write_text(text, encoding="utf-8")
        found = expected_text in text if expected_text else None
        status = "passed"
        if not text.strip():
            status = "empty_output"
        elif expected_text and not found:
            status = "expected_text_missing"
        result.update(
            status=status,
            url=url,
            output=str(output_path.resolve()),
            character_count=len(text),
            expected_text=expected_text,
            expected_text_found=found,
        )
    except Exception as exc:
        result.update(status="crawl_failed", error=f"{type(exc).__name__}: {exc}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--expect")
    parser.add_argument(
        "--output-dir",
        type=safe_output_dir,
        default=safe_output_dir("agent_outputs/component_evaluation"),
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "evaluation_id": "p3.1-optional-components-0.1",
        "protocol": "portable-agent-poc-0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frozen_application_called": False,
        "results": [
            evaluate_markitdown(args.docx, args.output_dir),
            asyncio.run(evaluate_crawl4ai(args.url, args.expect, args.output_dir)),
        ],
    }
    report_path = args.output_dir / "component-evaluation.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    failures = {
        "import_failed",
        "sample_missing",
        "conversion_failed",
        "empty_output",
        "crawl_failed",
        "expected_text_missing",
    }
    return 1 if any(item["status"] in failures for item in report["results"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
