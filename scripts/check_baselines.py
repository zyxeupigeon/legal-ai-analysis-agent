from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ROOT / "agent/core/v1.2/SYSTEM_PROMPT.md": "8e7b7156d2c1443020745b60e86b7f8370143f59f6be39a738d3be8977eaa379",
    ROOT / "agent/core/v1.2/WORKFLOW.md": "b3788e07695dff9af1a15a296d729b25450bd08459845f5c40a9e9b3e3b7bfa3",
    ROOT / "agent/skills/legal-report-review-and-verification/SKILL.md": "f7c502fa4908981276f1e0001fcc6b8572ad183a2c5848d9fd5acec33c5b72d4",
}


def normalized_sha256(path: Path) -> str:
    # Source artifacts do not end in a newline; repository text files do.
    data = path.read_bytes()
    if data.endswith(b"\n\n"):
        data = data[:-1]
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    failed = False
    for path, expected in EXPECTED.items():
        actual = normalized_sha256(path)
        if actual != expected:
            failed = True
            print(f"Baseline drift: {path.relative_to(ROOT)} expected={expected} actual={actual}")
    if failed:
        raise SystemExit(1)
    print(f"Verified {len(EXPECTED)} frozen baseline files.")


if __name__ == "__main__":
    main()
