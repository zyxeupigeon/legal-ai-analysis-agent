"""Create and verify a one-use session capability receipt before task allocation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import struct
import subprocess
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROTOCOL_ID = "portable-agent-1.1"
SCHEMA_VERSION = "1.1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GATE_ROOT = PROJECT_ROOT / "tmp" / "session_preflight"
CHALLENGE_ROOT = GATE_ROOT / "challenges"
RECEIPT_ROOT = GATE_ROOT / "receipts"
REQUIRED_CAPABILITIES = (
    "internet_search",
    "page_reading",
    "word_generation",
    "pdf_png_rendering",
    "direct_image_inspection",
)


DIGITS = {
    "0": ("11111", "10001", "10011", "10101", "11001", "10001", "11111"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("11110", "00001", "00001", "11110", "10000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("10010", "10010", "10010", "11111", "00010", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01111", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "11110"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("receipt timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("receipt timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def verify_project_binding() -> None:
    if Path.cwd().resolve() != PROJECT_ROOT:
        raise RuntimeError(f"current working directory must be project root: {PROJECT_ROOT}")
    declared = os.environ.get("LEGAL_AI_PROJECT_ROOT")
    if declared and Path(declared).resolve() != PROJECT_ROOT:
        raise RuntimeError("LEGAL_AI_PROJECT_ROOT does not match this project copy")


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_visual_probe(path: Path, code: str) -> None:
    width, height, scale = 720, 240, 18
    pixels = bytearray([255]) * (width * height * 3)
    glyph_width = 5 * scale
    gap = 2 * scale
    total_width = len(code) * glyph_width + (len(code) - 1) * gap
    origin_x = (width - total_width) // 2
    origin_y = (height - 7 * scale) // 2
    for offset, character in enumerate(code):
        pattern = DIGITS[character]
        glyph_x = origin_x + offset * (glyph_width + gap)
        for row, line in enumerate(pattern):
            for column, enabled in enumerate(line):
                if enabled != "1":
                    continue
                for dy in range(scale):
                    start = ((origin_y + row * scale + dy) * width + glyph_x + column * scale) * 3
                    pixels[start : start + scale * 3] = b"\x12\x2d\x49" * scale
    raw = b"".join(
        b"\x00" + bytes(pixels[row * width * 3 : (row + 1) * width * 3])
        for row in range(height)
    )
    data = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=False)
    path.write_bytes(data)


def challenge_digest(challenge_id: str, code: str) -> str:
    return hashlib.sha256(f"{challenge_id}:{code}".encode("ascii")).hexdigest()


def prepare_challenge() -> tuple[str, Path]:
    verify_project_binding()
    challenge_id = secrets.token_hex(12)
    code = f"{secrets.randbelow(1_000_000):06d}"
    directory = CHALLENGE_ROOT / challenge_id
    image_path = directory / "visual-probe.png"
    write_visual_probe(image_path, code)
    now = utc_now()
    atomic_write_json(directory / "challenge.json", {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "challenge_id": challenge_id,
        "project_root": str(PROJECT_ROOT),
        "created_at": iso(now),
        "expires_at": iso(now + timedelta(minutes=30)),
        "visual_code_sha256": challenge_digest(challenge_id, code),
        "visual_probe_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
    })
    return challenge_id, image_path


def verify_challenge(args: argparse.Namespace) -> Path:
    verify_project_binding()
    directory = (CHALLENGE_ROOT / args.challenge_id).resolve()
    if not directory.is_relative_to(CHALLENGE_ROOT.resolve()):
        raise ValueError("challenge path escaped the session preflight directory")
    payload = json.loads((directory / "challenge.json").read_text(encoding="utf-8"))
    if payload.get("protocol_id") != PROTOCOL_ID or payload.get("challenge_id") != args.challenge_id:
        raise ValueError("challenge does not match this protocol or identifier")
    if Path(str(payload.get("project_root", ""))).resolve() != PROJECT_ROOT:
        raise ValueError("challenge belongs to another project copy")
    if parse_timestamp(payload.get("expires_at")) < utc_now():
        raise ValueError("challenge expired; prepare a new session probe")
    if payload.get("visual_code_sha256") != challenge_digest(args.challenge_id, args.visual_code):
        raise ValueError("visual code is incorrect; do not declare READY without direct image inspection")
    visual_channel = (args.visual_channel or "").strip()
    if not visual_channel:
        raise ValueError("a visual channel must be declared with --visual-channel")
    if visual_channel != "human":
        if not args.visual_channel_evidence:
            raise ValueError(
                "non-human visual channels require --visual-channel-evidence "
                "(channel call record with probe image SHA-256)"
            )
        evidence_path = Path(args.visual_channel_evidence).resolve()
        if not evidence_path.is_file():
            raise ValueError(f"visual channel evidence file not found: {evidence_path}")
    else:
        evidence_path = None
    declarations = {
        "internet_search": args.internet_search,
        "page_reading": args.page_reading,
        "word_generation": args.word_generation,
        "pdf_png_rendering": args.pdf_png_rendering,
        "direct_image_inspection": "READY",
    }
    blocked = [name for name, status in declarations.items() if status != "READY"]
    if blocked:
        raise ValueError("required session capabilities are not READY: " + ", ".join(blocked))
    self_test = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "self_test_document_pipeline.py")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if self_test.returncode != 0 or "SELF_TEST_OK" not in self_test.stdout:
        detail = (self_test.stdout + "\n" + self_test.stderr).strip()
        raise RuntimeError("document self-test failed: " + detail)
    receipt_id = secrets.token_hex(16)
    now = utc_now()
    receipt_path = RECEIPT_ROOT / f"{receipt_id}.json"
    evidence_sha256 = (
        hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        if evidence_path is not None
        else None
    )
    atomic_write_json(receipt_path, {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "receipt_id": receipt_id,
        "challenge_id": args.challenge_id,
        "project_root": str(PROJECT_ROOT),
        "created_at": iso(now),
        "expires_at": iso(now + timedelta(hours=2)),
        "used_at": None,
        "used_for_task_id": None,
        "visual_probe_verified": True,
        "visual_channel": visual_channel,
        "visual_channel_evidence_sha256": evidence_sha256,
        "document_self_test": "READY",
        "capabilities": declarations,
    })
    shutil.rmtree(directory)
    return receipt_path.resolve()


def validate_capability_receipt(
    receipt_path: Path, project_root: Path, *, require_unused: bool = True
) -> dict:
    project_root = project_root.resolve()
    expected_root = (project_root / "tmp" / "session_preflight" / "receipts").resolve()
    receipt_path = receipt_path.resolve()
    if not receipt_path.is_relative_to(expected_root):
        raise ValueError("capability receipt must be inside this project tmp/session_preflight/receipts")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("capability receipt schema version is invalid")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"capability receipt protocol must be {PROTOCOL_ID}")
    if Path(str(payload.get("project_root", ""))).resolve() != project_root:
        raise ValueError("capability receipt belongs to another project copy")
    if parse_timestamp(payload.get("expires_at")) < utc_now():
        raise ValueError("capability receipt expired; run the session preflight again")
    if require_unused and payload.get("used_at") is not None:
        raise ValueError("capability receipt was already used")
    if payload.get("visual_probe_verified") is not True:
        raise ValueError("capability receipt has no verified visual probe")
    visual_channel = payload.get("visual_channel")
    if not isinstance(visual_channel, str) or not visual_channel.strip():
        raise ValueError("capability receipt has no declared visual channel")
    if visual_channel != "human":
        evidence_sha256 = payload.get("visual_channel_evidence_sha256")
        if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64:
            raise ValueError(
                "capability receipt for a non-human visual channel has no evidence SHA-256"
            )
    if payload.get("document_self_test") != "READY":
        raise ValueError("capability receipt has no successful document self-test")
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("capability receipt has no capability declarations")
    missing = [name for name in REQUIRED_CAPABILITIES if capabilities.get(name) != "READY"]
    if missing:
        raise ValueError("capability receipt is missing READY capabilities: " + ", ".join(missing))
    return payload


def consume_capability_receipt(receipt_path: Path, task_id: str, project_root: Path) -> dict:
    payload = validate_capability_receipt(receipt_path, project_root, require_unused=True)
    payload["used_at"] = iso(utc_now())
    payload["used_for_task_id"] = task_id
    atomic_write_json(receipt_path.resolve(), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare")
    verify = commands.add_parser("verify")
    verify.add_argument("--challenge-id", required=True)
    verify.add_argument("--visual-code", required=True)
    verify.add_argument(
        "--visual-channel",
        required=True,
        help="actual reader of the probe image: 'human' or an approved visual adapter channel id",
    )
    verify.add_argument(
        "--visual-channel-evidence",
        default=None,
        help="path to the channel call record JSON (required unless --visual-channel human)",
    )
    for option in ("internet-search", "page-reading", "word-generation", "pdf-png-rendering"):
        verify.add_argument(f"--{option}", required=True, choices=("READY", "BLOCKED"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "prepare":
            challenge_id, image_path = prepare_challenge()
            print("SESSION_PROBE_CREATED")
            print(f"CHALLENGE_ID={challenge_id}")
            print(f"PROBE_IMAGE={image_path.resolve()}")
            print("Read the six-digit code using the same direct image-view capability intended for final report pages.")
        else:
            receipt_path = verify_challenge(args)
            print("SESSION_CAPABILITY_READY")
            print(f"CAPABILITY_RECEIPT={receipt_path}")
    except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
        print("SESSION_CAPABILITY_BLOCKED")
        print(f"- {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
