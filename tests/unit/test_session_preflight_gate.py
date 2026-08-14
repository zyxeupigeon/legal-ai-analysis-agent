from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from scripts import session_preflight_gate as gate


def configure_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    gate_root = project_root / "tmp" / "session_preflight"
    monkeypatch.setattr(gate, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(gate, "GATE_ROOT", gate_root)
    monkeypatch.setattr(gate, "CHALLENGE_ROOT", gate_root / "challenges")
    monkeypatch.setattr(gate, "RECEIPT_ROOT", gate_root / "receipts")
    monkeypatch.chdir(project_root)
    monkeypatch.delenv("LEGAL_AI_PROJECT_ROOT", raising=False)
    tokens = iter(("challenge-id", "receipt-id"))
    monkeypatch.setattr(gate.secrets, "token_hex", lambda size: next(tokens))
    monkeypatch.setattr(gate.secrets, "randbelow", lambda maximum: 123456)
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "SELF_TEST_OK\n", ""),
    )
    return project_root


def ready_args(challenge_id: str, visual_code: str) -> argparse.Namespace:
    return argparse.Namespace(
        challenge_id=challenge_id,
        visual_code=visual_code,
        internet_search="READY",
        page_reading="READY",
        word_generation="READY",
        pdf_png_rendering="READY",
    )


def test_visual_probe_creates_one_use_bound_receipt(monkeypatch, tmp_path) -> None:
    project_root = configure_gate(monkeypatch, tmp_path)
    challenge_id, image_path = gate.prepare_challenge()

    assert challenge_id == "challenge-id"
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    receipt_path = gate.verify_challenge(ready_args(challenge_id, "123456"))
    receipt = gate.validate_capability_receipt(receipt_path, project_root)
    assert receipt["visual_probe_verified"] is True
    assert receipt["capabilities"]["direct_image_inspection"] == "READY"

    consumed = gate.consume_capability_receipt(receipt_path, "task-1", project_root)
    assert consumed["used_for_task_id"] == "task-1"
    with pytest.raises(ValueError, match="already used"):
        gate.validate_capability_receipt(receipt_path, project_root)


def test_wrong_visual_code_cannot_create_receipt(monkeypatch, tmp_path) -> None:
    configure_gate(monkeypatch, tmp_path)
    challenge_id, _ = gate.prepare_challenge()

    with pytest.raises(ValueError, match="visual code is incorrect"):
        gate.verify_challenge(ready_args(challenge_id, "654321"))

    assert not list(gate.RECEIPT_ROOT.glob("*.json"))


def test_receipt_from_another_project_is_rejected(monkeypatch, tmp_path) -> None:
    project_root = configure_gate(monkeypatch, tmp_path)
    challenge_id, _ = gate.prepare_challenge()
    receipt_path = gate.verify_challenge(ready_args(challenge_id, "123456"))
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["project_root"] = str(tmp_path / "other")
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="another project copy"):
        gate.validate_capability_receipt(receipt_path, project_root)
