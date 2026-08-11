"""Extract reference-document text for an Agent without making it a hard dependency.

DOCX files always have a standard-library fallback.  MarkItDown is used only when
it is already installed and imports successfully.  Outputs are restricted to
agent_outputs so user source files are never overwritten.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "agent_outputs"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


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


def distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def element_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{W}t")).strip()


def docx_to_markdown(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        damaged = archive.testzip()
        if damaged:
            raise ValueError(f"corrupt DOCX member: {damaged}")
        root = ET.fromstring(archive.read("word/document.xml"))

    body = root.find(f"{W}body")
    if body is None:
        return ""

    blocks: list[str] = []
    for child in body:
        if child.tag == f"{W}p":
            text = element_text(child)
            if text:
                blocks.append(text)
        elif child.tag == f"{W}tbl":
            rows: list[list[str]] = []
            for row in child.findall(f"{W}tr"):
                cells = [element_text(cell).replace("|", "\\|") for cell in row.findall(f"{W}tc")]
                if cells:
                    rows.append(cells)
            if rows:
                width = max(len(row) for row in rows)
                normalized = [row + [""] * (width - len(row)) for row in rows]
                blocks.append("| " + " | ".join(normalized[0]) + " |")
                blocks.append("| " + " | ".join(["---"] * width) + " |")
                blocks.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n\n".join(blocks)


def markitdown_to_markdown(path: Path) -> str:
    from markitdown import MarkItDown

    return MarkItDown().convert(str(path)).text_content


def extract(path: Path, engine: str) -> tuple[str, str, str | None]:
    markitdown_version = distribution_version("markitdown")
    markitdown_error = None
    if engine in {"auto", "markitdown"} and markitdown_version:
        try:
            return markitdown_to_markdown(path), "markitdown", markitdown_version
        except Exception as exc:
            markitdown_error = f"{type(exc).__name__}: {exc}"
            if engine == "markitdown":
                raise RuntimeError(markitdown_error) from exc

    if path.suffix.lower() == ".docx" and engine in {"auto", "stdlib-docx"}:
        return docx_to_markdown(path), "stdlib-docx", markitdown_error

    if markitdown_error:
        raise RuntimeError(
            f"MarkItDown failed and no fallback supports {path.suffix}: {markitdown_error}"
        )
    raise RuntimeError(
        f"No extractor is available for {path.suffix or 'this file type'}; "
        "install the optional MarkItDown dependency or provide DOCX"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--engine", choices=["auto", "markitdown", "stdlib-docx"], default="auto"
    )
    parser.add_argument(
        "--output-dir",
        type=safe_output_dir,
        default=safe_output_dir("agent_outputs/reference_extraction"),
    )
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        parser.error(f"source file does not exist: {source}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        text, selected_engine, fallback_detail = extract(source, args.engine)
    except Exception as exc:
        print(f"REFERENCE_EXTRACTION_FAIL {type(exc).__name__}: {exc}")
        return 1
    if not text.strip():
        print("REFERENCE_EXTRACTION_FAIL empty output")
        return 1

    markdown_path = args.output_dir / "reference-content.md"
    metadata_path = args.output_dir / "reference-extraction.json"
    markdown_path.write_text(text, encoding="utf-8")
    metadata = {
        "extraction_id": "portable-reference-extraction-0.1",
        "source": str(source),
        "engine": selected_engine,
        "fallback_detail": fallback_detail,
        "character_count": len(text),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "visual_fidelity_claimed": False,
        "output": str(markdown_path.resolve()),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"REFERENCE_EXTRACTION_OK engine={selected_engine} "
        f"characters={len(text)} output={markdown_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
