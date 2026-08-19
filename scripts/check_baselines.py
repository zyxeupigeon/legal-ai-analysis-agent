from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ROOT / "agent/core/v1.2/SYSTEM_PROMPT.md": "bda404c57f226cbf4ea49fe14f6054d9182c26cecee61b8fbc73384a3ff3326a",
    ROOT / "agent/core/v1.2/WORKFLOW.md": "b130032167f72831ea4f8b9a86e859c8a002a7b4521fd2d8a54aa67bf6946fae",
    ROOT / "agent/skills/legal-report-review-and-verification/SKILL.md": "8d6ea11ee7656e4a41fdd7e35ab7cacebff8acb95ec8b5b78c47a70b381fe8e5",
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
