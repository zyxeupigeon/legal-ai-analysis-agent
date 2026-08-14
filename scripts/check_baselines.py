from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ROOT / "agent/core/v1.1/SYSTEM_PROMPT.md": "44d8e51e7016a7d431a95b3f67e1b519102caf996a3a319593191c6319a24596",
    ROOT / "agent/core/v1.1/WORKFLOW.md": "eab9919c5746c86babb04038bfa0ff2083cf16afceb748384f588e71ab49e6f4",
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
