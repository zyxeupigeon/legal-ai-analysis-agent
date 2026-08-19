from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ROOT / "agent/core/v1.2/SYSTEM_PROMPT.md": "cfff8516317d9f9297e6787242cbb51577acfba54b72923f7cb643f2a1061ede",
    ROOT / "agent/core/v1.2/WORKFLOW.md": "018f7e727bb3bae82d7cb758ced012926364a0595a0782a91122238a16cc1e7c",
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
