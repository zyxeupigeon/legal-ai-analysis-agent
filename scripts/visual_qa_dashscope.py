#!/usr/bin/env python3
"""Visual QA helper for report pages and preflight probe reading via DashScope native API.

Two modes:
  python scripts/visual_qa_dashscope.py <png|dir> [...]                      # page layout QA
  python scripts/visual_qa_dashscope.py --read-probe <png> [--evidence-out <path>]

The --read-probe mode reads the six-digit code from a session preflight probe
image and writes a verifiable channel call record (image SHA-256, channel id,
timestamp, raw output). Per protocol portable-agent-1.1, a probe code may be
obtained only from a declared, approved visual adapter channel or the user's
own eyes - never from OCR, PDF geometry, source hashes, or an undeclared model.

Page QA mode remains AI-assisted only; final acceptance still requires a human
visual review.

The DashScope key is read from the DASHSCOPE_API_KEY environment variable,
falling back to env.ANTHROPIC_AUTH_TOKEN in ~/.claude/settings.qwen-vision.json.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DASH_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3-vl-plus"
PROTOCOL_ID = "portable-agent-1.1"
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

PROMPT = (
    "你是一个法律AI产品分析报告的版面质检员。请逐项检查这张报告页面图片，并如实回答：\n"
    "1) 是否存在内容被裁切、超出页面边缘或丢失\n"
    "2) 是否存在文字重叠或互相遮挡\n"
    "3) 是否存在缺字、乱码或明显异常空白\n"
    "4) 表格是否越界，或跨页后失去列含义\n"
    "5) 是否存在孤立标题（标题在页末、正文在下一页）或其他分页问题\n"
    "6) 其他明显版式问题\n"
    "输出格式：先给一行结论“版面OK”或“发现问题”，然后逐条列出具体问题（若没有可省略），"
    "最后一行给出建议修复动作。只基于图片中实际可见内容判断，不要臆测或补充图片之外的信息。"
)

PROBE_PROMPT = (
    "图片中央有一组深色大号数字，正好 6 位，第一位可能是 0。"
    "请只输出这 6 位数字本身，保持完整 6 位（若第一位是 0 必须输出 0），"
    "不要输出任何解释、标点或额外文字，也不要猜测图片之外的内容。"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_key() -> str | None:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if key:
        return key
    vision_cfg = Path.home() / ".claude" / "settings.qwen-vision.json"
    if vision_cfg.exists():
        try:
            cfg = json.loads(vision_cfg.read_text(encoding="utf-8"))
            return cfg.get("env", {}).get("ANTHROPIC_AUTH_TOKEN")
        except (OSError, json.JSONDecodeError):
            return None
    return None


def collect_images(paths: list[str]) -> list[Path]:
    images: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            render_dir = path / "render"
            if render_dir.is_dir():
                images.extend(sorted(render_dir.glob("page-*.png")))
            images.extend(sorted(path.glob("page-*.png")))
        elif path.is_file() and path.suffix.lower() in MEDIA_TYPES:
            images.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for image in images:
        resolved = image.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(image)
    return unique


def qa_image(image_path: Path, key: str, prompt: str = PROMPT) -> str:
    suffix = image_path.suffix.lower()
    media_type = MEDIA_TYPES.get(suffix, "image/png")
    data_url = (
        f"data:{media_type};base64,"
        + base64.b64encode(image_path.read_bytes()).decode("ascii")
    )
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        DASH_BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def read_probe(
    image_path: Path, key: str, evidence_out: Path, max_attempts: int = 3
) -> str:
    """Read the six-digit preflight code via the visual channel and write an evidence record.

    When the probe image lives under a session_preflight challenge directory, the
    challenge's stored hash is used to verify the code; mismatches retry up to
    max_attempts. Without challenge context the first six-digit output is accepted
    and marked as unverified.
    """
    resolved = image_path.resolve()
    challenge_id: str | None = None
    expected_sha: str | None = None
    if resolved.parent.parent.name == "challenges":
        challenge_id = resolved.parent.name
        challenge_json = resolved.parent / "challenge.json"
        if challenge_json.is_file():
            try:
                payload = json.loads(challenge_json.read_text(encoding="utf-8"))
                if payload.get("protocol_id") == PROTOCOL_ID:
                    expected_sha = payload.get("visual_code_sha256")
            except (OSError, json.JSONDecodeError):
                expected_sha = None

    attempts = 0
    last_raw = ""
    while attempts < max_attempts:
        attempts += 1
        raw = qa_image(image_path, key, prompt=PROBE_PROMPT)
        last_raw = raw
        match = re.search(r"\d{6}", raw)
        if not match:
            continue
        if expected_sha and challenge_id:
            calc = hashlib.sha256(
                f"{challenge_id}:{match.group(0)}".encode("ascii")
            ).hexdigest()
            if calc == expected_sha:
                break
            continue
        break

    visual_code = ""
    verified = False
    match = re.search(r"\d{6}", last_raw)
    if match:
        visual_code = match.group(0)
        if expected_sha and challenge_id:
            verified = (
                hashlib.sha256(
                    f"{challenge_id}:{visual_code}".encode("ascii")
                ).hexdigest()
                == expected_sha
            )

    if not visual_code:
        raise RuntimeError(
            "visual channel did not return a six-digit code in "
            f"{attempts} attempt(s); last raw output: {last_raw[:200]!r}"
        )
    if expected_sha is not None and not verified:
        raise RuntimeError(
            f"visual code {visual_code} failed the challenge hash check after "
            f"{attempts} attempt(s); retry, or read the code with human eyes "
            "(--visual-channel human)"
        )

    evidence = {
        "schema": "visual_channel_evidence-1.1",
        "channel": MODEL,
        "model": MODEL,
        "image": str(resolved),
        "image_sha256": file_sha256(image_path),
        "challenge_id": challenge_id,
        "verified": verified if challenge_id else None,
        "attempts": attempts,
        "timestamp": utc_now_iso(),
        "raw_output": last_raw,
        "visual_code": visual_code,
    }
    evidence_out.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("PROBE_CODE_READ")
    print(f"VISUAL_CODE={visual_code}")
    print(f"VISUAL_CHANNEL={MODEL}")
    print(f"PROBE_IMAGE_SHA256={evidence['image_sha256']}")
    print(f"VERIFIED={str(verified).lower()}")
    print(f"ATTEMPTS={attempts}")
    print(f"EVIDENCE_FILE={evidence_out.resolve()}")
    return visual_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DashScope qwen3-vl helper: report page QA or preflight probe reading."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="PNG file(s) or directory(ies) containing page-*.png (QA mode)",
    )
    parser.add_argument(
        "--read-probe",
        default=None,
        metavar="PNG",
        help="read the six-digit code from a preflight probe PNG and write an evidence record",
    )
    parser.add_argument(
        "--evidence-out",
        default=None,
        metavar="PATH",
        help="evidence JSON output path (default: <probe>.evidence.json)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    key = load_key()
    if not key:
        print("ERROR: no DashScope key found. Set DASHSCOPE_API_KEY or check ~/.claude/settings.qwen-vision.json.")
        sys.exit(2)

    if args.read_probe:
        probe_path = Path(args.read_probe)
        if not probe_path.is_file():
            print(f"ERROR: probe image not found: {probe_path}")
            sys.exit(2)
        evidence_out = (
            Path(args.evidence_out)
            if args.evidence_out
            else probe_path.with_suffix(probe_path.suffix + ".evidence.json")
        )
        try:
            read_probe(probe_path, key, evidence_out)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            print(f"ERROR: probe read failed: {exc}")
            sys.exit(1)
        return

    images = collect_images(args.paths)
    if not images:
        print("ERROR: no page-*.png images found in the given paths.")
        sys.exit(2)
    print(f"Checking {len(images)} page image(s) with {MODEL} ...")
    failures = 0
    for image in images:
        print(f"\n===== {image} =====")
        try:
            print(qa_image(image, key))
        except urllib.error.HTTPError as exc:
            failures += 1
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            print(f"ERROR: DashScope returned {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures += 1
            print(f"ERROR: request failed: {exc}")
    print(f"\nDone: {len(images) - failures}/{len(images)} page(s) inspected.")
    print("NOTE: this is an AI-assisted check. Final acceptance still requires a human visual review.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
